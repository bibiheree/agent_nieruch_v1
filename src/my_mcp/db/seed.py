import sys
import os

sys.path.append(os.getcwd())

from src.my_mcp.db.session import SessionLocal, engine
from src.my_mcp.db.models import Base, Agent, Property, Appointment, RODOBlacklist

# Zamien te ID na prawdziwe ID kalendarzy z Google Calendar (Ustawienia kalendarza -> ID kalendarza)
AGENTS = [
    {
        "name": "Hubert",
        "phone": "+48123456789",
        "portal_id": "HUBERT-001",
        "google_calendar_id": "epic202012@gmail.com",
        "properties": [
            "ul. Bracka 4/12, Krakow",
            "ul. Grodzka 10, Krakow",
            "ul. Florianska 5, Krakow",
        ],
    },
    {
        "name": "Wiktoria",
        "phone": "+48111222333",
        "portal_id": "WIKTORIA-002",
        "google_calendar_id": "96e3daa8406aa28d1ac409213099e7ac4fed7722a7750ce9f66a9cbc25a64c8d@group.calendar.google.com",
        "properties": [
            "ul. Pilsudskiego 20, Krakow",
            "ul. Dietla 8, Krakow",
            "ul. Karmelicka 15, Krakow",
        ],
    },
    {
        "name": "Jakub",
        "phone": "+48444555666",
        "portal_id": "JAKUB-003",
        "google_calendar_id": "40b798fe606a7e6fd282aa973afe976bec7e3d51aa85862bd17db569a82c9591@group.calendar.google.com",
        "properties": [
            "ul. Wielicka 30, Krakow",
            "ul. Podgorzanska 2, Krakow",
            "ul. Limanowskiego 12, Krakow",
        ],
    },
]


def seed_data():
    print("--- ROZPOCZECIE SEEDOWANIA BAZY DANYCH (TECNOCASA) ---")

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Czyszczenie istniejacych tabel...")
        db.query(Appointment).delete()
        db.query(Property).delete()
        db.query(Agent).delete()
        db.query(RODOBlacklist).delete()
        db.commit()

        print("Dodawanie 3 agentow i ich nieruchomosci...")
        for agent_data in AGENTS:
            agent = Agent(
                name=agent_data["name"],
                phone=agent_data["phone"],
                portal_id=agent_data["portal_id"],
                google_calendar_id=agent_data["google_calendar_id"],
            )
            db.add(agent)
            db.flush()

            for address in agent_data["properties"]:
                db.add(Property(address=address, agent_id=agent.id))

            print(f"  -> {agent.name}: {len(agent_data['properties'])} nieruchomosci")

        print("Dodawanie przykladowego numeru na czarna liste RODO...")
        db.add(RODOBlacklist(phone="+48999888777"))

        db.commit()
        print("--- SEEDOWANIE BAZY ZAKONCZONE SUKCESEM ---")
        print("UWAGA: Jesli zmieniles modele, usun plik data/app.db przed seedem.")

    except Exception as e:
        db.rollback()
        print(f"BLAD PODCZAS SEEDOWANIA BAZY DANYCH: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
