from __future__ import annotations
import os
import sys
import random
import asyncio
from datetime import datetime
import uvicorn
from fastmcp import FastMCP
from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

# Dodanie katalogu głównego do path, aby importy lokalne działały w kontenerze
sys.path.append(os.getcwd())

from src.my_mcp.db.session import SessionLocal, engine
from src.my_mcp.db.models import Base, SMSLog, RODOBlacklist

# Inicjalizacja FastMCP
mcp = FastMCP("Tecnocasa-SMS-Core")

# ---------------------------------------------------------------------
# DYNAMICZNE WYKRYWANIE APLIKACJI ASGI (Odporność na wersje biblioteki)
# Przeszukuje znane atrybuty FastMCP w celu pobrania instancji FastAPI
# ---------------------------------------------------------------------
app = None
for attr in ["get_asgi_app", "asgi_app", "app", "_app", "_asgi_app"]:
    if hasattr(mcp, attr):
        candidate = getattr(mcp, attr)
        if callable(candidate):
            try:
                app = candidate()
            except Exception:
                continue
        else:
            app = candidate
        if app is not None:
            print(f"DEBUG: Wykryto aplikacje FastAPI przy uzyciu atrybutu: '{attr}'")
            break

if app is None:
    # Fallback: Jeśli żadna metoda nie zadziałała, tworzymy nową czystą instancję FastAPI
    from fastapi import FastAPI

    app = FastAPI(title="Tecnocasa-SMS-Core-Fallback")
    print("DEBUG: OSTRZEZENIE: Nie znaleziono aplikacji ASGI w FastMCP. Uruchomiono fallback FastAPI.")

# Szablony wiadomości bez polskich znaków (Wariant Budżetowy - Dokładnie 1 SMS rozliczeniowy)
SMS_TEMPLATE_STANDARD = "Dzien dobry, przypominamy o dzisiejszej wizycie o godz. {time} na ul. {address}. Agent {agent}"
SMS_TEMPLATE_UPDATE = "AKTUALIZACJA: Przypominamy o nowej godzinie dzisiejszej wizyty o godz. {time} na ul. {address}. Agent {agent}"


def init_db():
    """Inicjalizacja tabel za pomocą SQLAlchemy ORM przy starcie aplikacji"""
    Base.metadata.create_all(bind=engine)
    print("DEBUG: Tabele bazy danych zostały pomyślnie zsynchronizowane przez SQLAlchemy ORM.")


# ---------------------------------------------------------------------
# ASYNCHRONICZNE ZADANIA W TLE (Symulacja Bramki GSM i raportów doręczeń)
# ---------------------------------------------------------------------
async def simulate_dlr_callback(log_id: int):
    """
    Symuluje asynchroniczny raport doręczenia (DLR) od operatora komórkowego.
    Czeka 5 sekund, po czym losowo (95% szans na sukces, 5% na błąd) aktualizuje status w bazie.
    """
    await asyncio.sleep(5)
    db = SessionLocal()
    try:
        log_entry = db.query(SMSLog).filter(SMSLog.id == log_id).first()
        if log_entry and log_entry.status == "PENDING":
            # Losowy status doręczenia
            new_status = "DELIVERED" if random.random() < 0.95 else "FAILED"
            log_entry.status = new_status
            db.commit()
            print(f" [BRAMKA SMS API] Asynchroniczny DLR dla logu ID {log_id}: Status zmieniony na {new_status}")
    except Exception as e:
        print(f"ERROR w zadaniu w tle DLR: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------------
# RDZEŃ LOGIKI BIZNESOWEJ (Zgodny z Clean Architecture)
# ---------------------------------------------------------------------
def check_sms_status_orm(db: Session, google_event_id: str, scheduled_time: str, sms_type: str) -> bool:
    """Sprawdza w bazie ORM, czy dokładnie ten termin spotkania otrzymał już przypomnienie"""
    return db.query(SMSLog).filter(
        SMSLog.google_event_id == google_event_id,
        SMSLog.scheduled_time == scheduled_time,
        SMSLog.sms_type == sms_type
    ).first() is not None


def check_rodo_blacklist(db: Session, phone: str) -> bool:
    """Sprawdza czy numer telefonu znajduje się na czarnej liście RODO"""
    return db.query(RODOBlacklist).filter(RODOBlacklist.phone == phone).first() is not None


def process_sms_delivery(
        db: Session,
        background_tasks: BackgroundTasks,
        google_event_id: str,
        scheduled_time: str,
        phone: str,
        client_name: str,
        time_str: str,
        address_str: str,
        agent_name: str,
        sms_type: str = "REMINDER"
) -> str:
    """
    Główna orkiestracja wysyłki:
    1. Sprawdza czarną listę RODO.
    2. Sprawdza idempotentność (duplikaty na parze ID + godzina).
    3. Wykrywa, czy to pierwsze przypomnienie, czy aktualizacja terminu (Rescheduling).
    4. Tworzy wpis ze statusem PENDING i odpala asynchroniczny DLR w tle.
    """
    # 1. Zabezpieczenie RODO
    if check_rodo_blacklist(db, phone):
        log_entry = SMSLog(
            google_event_id=google_event_id,
            scheduled_time=scheduled_time,
            client_phone=phone,
            sms_type=sms_type,
            status="BLOCKED_BY_RODO_COMPLIANCE",
            message_body="[ZABLOKOWANO PRZEZ RODO]"
        )
        db.add(log_entry)
        db.commit()
        return f"ANULOWANO: Numer {phone} znajduje się na czarnej liście RODO."

    # 2. Idempotentność na kompozycie (google_event_id + scheduled_time)
    if check_sms_status_orm(db, google_event_id, scheduled_time, sms_type):
        return f"ANULOWANO: Przypomnienie na godzinę {time_str} zostało już wysłane."

    # 3. Wykrywanie przebukowania (Rescheduling)
    has_prior_sms = db.query(SMSLog).filter(
        SMSLog.google_event_id == google_event_id,
        SMSLog.scheduled_time != scheduled_time
    ).first() is not None

    template = SMS_TEMPLATE_UPDATE if has_prior_sms else SMS_TEMPLATE_STANDARD

    try:
        message = template.format(
            time=time_str,
            address=address_str,
            agent=agent_name
        )
    except KeyError as e:
        return f"BŁĄD SZABLONU: Brakujący klucz formatowania: {str(e)}"

    # Wyświetlenie ramki w konsoli Dockera
    border = "=" * 60
    print(f"\n{border}")
    print(f" [BRAMKA SMS] WYSOKA PRIORYTETOWOŚĆ - TYP: {sms_type} {'(AKTUALIZACJA)' if has_prior_sms else ''}")
    print(f" Do: {phone} ({client_name})")
    print(f" Treść: {message}")
    print(f" Długość: {len(message)} znaków")
    print(f" Status początkowy: PENDING (Zlecono asynchroniczny raport DLR)")
    print(f"{border}\n")

    # 4. Zapis do bazy ze statusem PENDING i przekazanie zadania do Background Tasks
    try:
        new_log = SMSLog(
            google_event_id=google_event_id,
            scheduled_time=scheduled_time,
            client_phone=phone,
            sms_type=sms_type,
            status="PENDING",
            message_body=message
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)

        # Uruchomienie symulacji raportu doręczenia w tle za 5 sekund
        background_tasks.add_task(simulate_dlr_callback, new_log.id)

        msg_type_desc = "aktualizacja" if has_prior_sms else "standard"
        return f"SUKCES: SMS ({msg_type_desc}) zarejestrowany jako PENDING dla {phone}."
    except Exception as e:
        db.rollback()
        return f"BŁĄD ZAPISU DO BAZY ORM: {str(e)}"


# =====================================================================
# NARZĘDZIA PROWADZĄCE MCP (Model Context Protocol dla Agentów AI)
# =====================================================================
@mcp.tool()
def add_number_to_rodo_blacklist(phone: str) -> str:
    """Dodaje podany numer telefonu na czarną listę RODO, uniemożliwiając wysyłkę."""
    db = SessionLocal()
    try:
        if check_rodo_blacklist(db, phone):
            return f"Numer {phone} już znajduje się na czarnej liście."
        blacklist_entry = RODOBlacklist(phone=phone)
        db.add(blacklist_entry)
        db.commit()
        return f"SUKCES: Numer {phone} został trwale wpisany na czarną listę RODO."
    except Exception as e:
        db.rollback()
        return f"Błąd bazy danych przy dodawaniu do RODO: {e}"
    finally:
        db.close()


# =====================================================================
# REST ENDPOINTS DLA INTEGRACJI Z n8n (rejestrowane na aplikacji FastAPI)
# =====================================================================
@app.post("/tools/check_sms_status")
async def api_check_sms_status(data: dict):
    google_event_id = data.get("google_event_id")
    scheduled_time = data.get("scheduled_time")
    sms_type = data.get("sms_type", "REMINDER")

    if not google_event_id or not scheduled_time:
        raise HTTPException(status_code=400, detail="Missing required 'google_event_id' or 'scheduled_time' parameter.")

    db = SessionLocal()
    try:
        sent = check_sms_status_orm(db, google_event_id, scheduled_time, sms_type)
        return {"sent": sent}
    finally:
        db.close()


@app.post("/tools/mock_send_sms")
async def api_mock_send_sms(data: dict, background_tasks: BackgroundTasks):
    google_event_id = data.get("google_event_id")
    scheduled_time = data.get("scheduled_time")
    phone = data.get("phone")
    client_name = data.get("client_name")
    time_str = data.get("time_str")
    address_str = data.get("address_str")
    agent_name = data.get("agent_name")
    sms_type = data.get("sms_type", "REMINDER")

    if not all([google_event_id, scheduled_time, phone, client_name, time_str, address_str, agent_name]):
        raise HTTPException(status_code=400, detail="Missing required parameters in JSON body.")

    db = SessionLocal()
    try:
        result = process_sms_delivery(
            db=db,
            background_tasks=background_tasks,
            google_event_id=google_event_id,
            scheduled_time=scheduled_time,
            phone=phone,
            client_name=client_name,
            time_str=time_str,
            address_str=address_str,
            agent_name=agent_name,
            sms_type=sms_type
        )
        return {"result": result}
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    # Bezpośrednie uruchomienie serwera ASGI za pomocą uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)