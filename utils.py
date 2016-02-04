

def is_number(var):
    try:
        value = int(var)
    except Exception:
        return False
    return True
