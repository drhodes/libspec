from libspec.spec import API

class UserAPI(API):
    """
    API Specification: {{api_name}}
    """
    def get_user(self, user_id: int) -> dict:
        """Fetch a user by ID."""
        pass

    def create_user(self, username: str, email: str) -> dict:
        """Create a new user."""
        pass
        
    def constraints(self):
        return ["Must be authenticated.", "Rate limited to 100 req/min."]
