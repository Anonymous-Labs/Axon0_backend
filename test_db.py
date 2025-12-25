import asyncio
from app.database import create_tables

async def test():
    try:
        await create_tables()
        print("Tables created successfully")
    except Exception as e:
        print(f"Error creating tables: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
