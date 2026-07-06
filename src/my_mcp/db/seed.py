import sys
import os
from datetime import datetime, timedelta

# Dodanie głównego folderu do PYTHONPATH, aby importy działały poprawnie w Dockerze i lokalnie
sys.path.append(os.getcwd())

from src.my_mcp.db.session import SessionLocal, engine
from src.my_mcp.db.models import Base, Agent, Property, Appointment, RODOBlacklist


def seed_data():
    print("--- ROZPOCZECIE SEEDOWANIA BAZY DANYCH (TECNOCASA) ---")

    # Tworzenie tabel, jeśli jeszcze nie istnieją (na podstawie definicji z Canvas)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Czyszczenie starych danych dla zachowania powtarzalności testów
        print("Czyszczenie istniejacych tabel...")
        db.query(Appointment).delete()
        db.query(Property).delete()
        db.query(Agent).delete()
        db.query(RODOBlacklist).delete()
        db.commit()

        print("Dodawanie agenta testowego...")
        agent_hubert = Agent(
            name="Hubert Inzynier",
            phone="+48123456789",
            portal_id="ABC-123"  # ID uzywane przy weryfikacji i matchowaniu ogłoszen
        )
        db.add(agent_hubert)
        db.flush()  # Pobranie wygenerowanego ID agenta bez pelnego commitowania transakcji

        print("Dodawanie nieruchomosci testowych...")
        prop1 = Property(
            address="ul. Bracka 4/12, Krakow",
            agent_id=agent_hubert.id
        )
        prop2 = Property(
            address="ul. Grodzka 10, Krakow",
            agent_id=agent_hubert.id
        )
        db.add_all([prop1, prop2])
        db.flush()

        print("Dodawanie planowanych spotkan na dzis...")
        # Spotkanie 1: Zaplanowane za 2 godziny
        appt1 = Appointment(
            property_id=prop1.id,
            client_name="Jan Kowalski",
            client_phone="+48600700800",
            scheduled_at=datetime.now() + timedelta(hours=2)
        )
        # Spotkanie 2: Zaplanowane za 5 godzin
        appt2 = Appointment(
            property_id=prop2.id,
            client_name="Anna Nowak",
            client_phone="+48501502503",
            scheduled_at=datetime.now() + timedelta(hours=5)
        )
        db.add_all([appt1, appt2])

        print("Dodawanie przykladowego numeru na czarna liste RODO...")
        blocked_user = RODOBlacklist(
            phone="+48999888777"
        )
        db.add(blocked_user)

        db.commit()
        print("--- SEEDOWANIE BAZY ZAKONCZONE SUKCESEM ---")

    except Exception as e:
        db.rollback()
        print(f"BLAD PODCZAS SEEDOWANIA BAZY DANYCH: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()