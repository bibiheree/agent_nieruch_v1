from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

# Bazowa klasa deklaratywna dla modeli SQLAlchemy
Base = declarative_base()

class Agent(Base):
    """Model agenta nieruchomości (np. Ciebie!)"""
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    portal_id = Column(String, unique=True, nullable=True) # ID ogłoszeń np. Otodom, OLX

    # Relacja zwrotna: agent posiada wiele nieruchomości
    properties = relationship("Property", back_populates="agent")


class Property(Base):
    """Model nieruchomości przypisanej do agenta"""
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)

    # Powiązanie z agentem i spotkaniami
    agent = relationship("Agent", back_populates="properties")
    appointments = relationship("Appointment", back_populates="property")


class Appointment(Base):
    """Model planowanego spotkania (prezentacji lokalu)"""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    client_name = Column(String, nullable=False)
    client_phone = Column(String, nullable=False)
    scheduled_at = Column(DateTime, nullable=False)

    # Powiązanie z nieruchomością
    property = relationship("Property", back_populates="appointments")


class SMSLog(Base):
    """
    Model logów SMS z obsługą klucza kompozytowego i statusów DLR.
    Klucz logiczny google_event_id + scheduled_time chroni przed dublowaniem wysyłek.
    """
    __tablename__ = "sms_logs"

    id = Column(Integer, primary_key=True, index=True)
    google_event_id = Column(String, index=True, nullable=False)
    scheduled_time = Column(String, index=True, nullable=False) # Czas ISO jako wersja wydarzenia (Rescheduling)
    client_phone = Column(String, nullable=False)
    sms_type = Column(String, nullable=False)                   # Np. REMINDER, UPDATE, CANCEL
    status = Column(String, nullable=False)                     # PENDING, DELIVERED, FAILED, BLOCKED_BY_RODO_COMPLIANCE
    sent_at = Column(DateTime, default=datetime.utcnow)
    message_body = Column(String, nullable=True)


class RODOBlacklist(Base):
    """Model czarnej listy RODO - numery zablokowane przed automatyczną wysyłką"""
    __tablename__ = "rodo_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)