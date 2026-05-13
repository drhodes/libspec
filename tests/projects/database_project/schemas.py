from libspec.spec import SQLite3, PeeWee

class EventLogSQLite(SQLite3):
    """
    Event Log Database Schema
    """
    id: int
    event_type: str
    timestamp: str

    def dbpath(self):
        return "/var/log/events.db"

class UserPreferencesPeeWee(PeeWee):
    """
    User Preferences Schema
    """
    user_id: int
    theme: str
    notifications_enabled: bool

    def dbpath(self):
        return "/var/lib/prefs.db"
