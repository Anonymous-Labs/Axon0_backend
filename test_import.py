try:
    from app.models.user import User
    from app.models.memory import Memory, Feedback
    print("Models imported successfully")
except Exception as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()
