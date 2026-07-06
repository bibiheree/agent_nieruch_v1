from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from src.my_mcp.db.models import Agent, Appointment, Property


def upsert_appointment(
    db: Session,
    *,
    google_event_id: str,
    property_id: int,
    agent_id: int,
    client_name: str,
    client_phone: str,
    scheduled_at: datetime,
) -> tuple[Appointment, bool]:
    """
    Tworzy lub aktualizuje spotkanie po google_event_id.
    Zwraca (appointment, created) gdzie created=True oznacza nowy rekord.
    """
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if property_obj is None:
        raise ValueError(f"Nie znaleziono nieruchomosci o ID {property_id}.")

    if property_obj.agent_id != agent_id:
        raise ValueError(
            f"Nieruchomosc {property_id} nie nalezy do agenta {agent_id} "
            f"(przypisany agent: {property_obj.agent_id})."
        )

    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if agent is None:
        raise ValueError(f"Nie znaleziono agenta o ID {agent_id}.")

    existing = (
        db.query(Appointment)
        .filter(Appointment.google_event_id == google_event_id)
        .first()
    )

    if existing:
        existing.property_id = property_id
        existing.agent_id = agent_id
        existing.client_name = client_name
        existing.client_phone = client_phone
        existing.scheduled_at = scheduled_at
        db.commit()
        db.refresh(existing)
        return existing, False

    appointment = Appointment(
        google_event_id=google_event_id,
        property_id=property_id,
        agent_id=agent_id,
        client_name=client_name,
        client_phone=client_phone,
        scheduled_at=scheduled_at,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment, True


def list_agents(db: Session) -> list[dict]:
    agents = db.query(Agent).order_by(Agent.id).all()
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "phone": agent.phone,
            "portal_id": agent.portal_id,
            "google_calendar_id": agent.google_calendar_id,
        }
        for agent in agents
    ]


def list_properties(db: Session, agent_id: int | None = None) -> list[dict]:
    query = db.query(Property).order_by(Property.id)
    if agent_id is not None:
        query = query.filter(Property.agent_id == agent_id)

    properties = query.all()
    return [
        {
            "id": prop.id,
            "address": prop.address,
            "agent_id": prop.agent_id,
            "agent_name": prop.agent.name if prop.agent else None,
        }
        for prop in properties
    ]


def find_property_by_address(db: Session, address_fragment: str) -> Property | None:
    """Szuka nieruchomosci po fragmencie adresu (case-insensitive)."""
    fragment = address_fragment.strip().lower()
    if not fragment:
        return None

    for prop in db.query(Property).all():
        if fragment in prop.address.lower():
            return prop
    return None


def find_property_for_agent_by_address(
    db: Session,
    *,
    agent_id: int,
    address_fragment: str,
) -> Property | None:
    """Szuka nieruchomosci po adresie, ale tylko wsrod lokali danego agenta."""
    fragment = address_fragment.strip().lower()
    if not fragment:
        return None

    properties = db.query(Property).filter(Property.agent_id == agent_id).all()
    for prop in properties:
        if fragment in prop.address.lower():
            return prop
    return None


def get_agent_by_name(db: Session, agent_name: str) -> Agent | None:
    """Znajduje agenta po imieniu (nazwa kalendarza = imie agenta)."""
    needle = agent_name.strip().lower()
    if not needle:
        return None

    for agent in db.query(Agent).all():
        if agent.name.strip().lower() == needle:
            return agent
    return None


def get_agent_by_google_calendar_id(db: Session, google_calendar_id: str) -> Agent | None:
    """
    Znajduje agenta po ID kalendarza Google.
    Obsluguje dokladne dopasowanie oraz czesciowe (gdy n8n zwraca dluzsze ID).
    """
    needle = google_calendar_id.strip().lower()
    if not needle:
        return None

    for agent in db.query(Agent).filter(Agent.google_calendar_id.isnot(None)).all():
        stored = (agent.google_calendar_id or "").strip().lower()
        if not stored:
            continue
        if needle == stored or needle in stored or stored in needle:
            return agent
    return None


def resolve_agent_for_sms(
    db: Session,
    *,
    google_calendar_id: str | None = None,
    agent_id: int | None = None,
    agent_name: str | None = None,
) -> Agent:
    """
    Ustala agenta podpisujacego SMS.
    Priorytet: agent_name (nazwa kalendarza) -> agent_id -> google_calendar_id.
    """
    if agent_name:
        agent = get_agent_by_name(db, agent_name)
        if agent:
            return agent
        raise ValueError(
            f"Nie znaleziono agenta o imieniu: {agent_name}. "
            "Sprawdz tabele agents (GET /tools/agents) - imie musi zgadzac sie z nazwa kalendarza Google."
        )

    if agent_id is not None:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            return agent
        raise ValueError(f"Nie znaleziono agenta o ID {agent_id}.")

    if google_calendar_id:
        agent = get_agent_by_google_calendar_id(db, google_calendar_id)
        if agent:
            return agent
        raise ValueError(
            f"Nie znaleziono agenta dla kalendarza Google: {google_calendar_id}. "
            "Sprawdz google_calendar_id w tabeli agents (GET /tools/agents)."
        )

    raise ValueError(
        "Brak identyfikacji agenta. Podaj agent_name (zalecane), agent_id lub google_calendar_id."
    )


def agent_to_dict(agent: Agent) -> dict:
    return {
        "id": agent.id,
        "name": agent.name,
        "phone": agent.phone,
        "portal_id": agent.portal_id,
        "google_calendar_id": agent.google_calendar_id,
    }
