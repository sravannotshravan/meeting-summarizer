from pathlib import Path

from backend.database import initialize_database
from backend.storage import (
    create_meeting,
    get_meeting,
    update_meeting
)


initialize_database()


meeting = create_meeting(
    title="Deeaa Test Meeting",
    original_filename="deeaa.m4a"
)


print("Created meeting:")
print(meeting)

print()
print("Meeting ID:")
print(meeting.id)


update_meeting(
    meeting.id,
    status="transcribing"
)


loaded = get_meeting(
    meeting.id
)


print()
print("Loaded from database:")
print(loaded)