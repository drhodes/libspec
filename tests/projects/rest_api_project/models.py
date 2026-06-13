from libspec.spec import DataSchema


class UserSchema(DataSchema):
    """
    DATA-MODEL: {{model_name}}
    """

    id: int
    username: str
    email: str
