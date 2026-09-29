import asyncio
from app.services.notification_service import notification_service


async def main():
    print("🚀 Lancement du test SMTP CENTAURE...")
    res = await notification_service.send_email_async(
        recipient="eric.kuter@gouv.nc",
        subject="🚨 TEST CENTAURE SMTP FINAL",
        html_content="<h1 style='color: green;'>Victoire ! Le service d'alerte CENTAURE est 100% opérationnel !</h1>",
    )
    print("👉 Résultat final :", res)


if __name__ == "__main__":
    asyncio.run(main())
