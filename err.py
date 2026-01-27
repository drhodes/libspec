import inspect


class UnimplementedMethodError(NotImplementedError):
    """
    Custom exception for unimplemented methods that automatically
    includes the method name and class name using introspection.
    """
    
    def __init__(self, message=None):
        # Get the frame that called this exception
        frame = inspect.currentframe().f_back
        
        # Get the method name
        method_name = frame.f_code.co_name
        
        # Get the class name by inspecting 'self' or 'cls' in the frame's local variables
        class_name = None
        local_vars = frame.f_locals
        
        if 'self' in local_vars:
            class_name = local_vars['self'].__class__.__name__
        elif 'cls' in local_vars:
            class_name = local_vars['cls'].__name__
        
        # Build the error message
        if class_name:
            auto_message = f"Method '{method_name}' is not implemented in class '{class_name}'"
        else:
            auto_message = f"Method '{method_name}' is not implemented"
        
        # Use custom message if provided, otherwise use auto-generated one
        final_message = f"{auto_message}. {message}" if message else auto_message
        
        super().__init__(final_message)


