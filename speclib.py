"""
speclib - Lightweight library for evolving software specifications

Usage:
    from speclib import spec, layer, interface, implements
    
    @layer("domain")
    class MyClass:
        @spec
        def my_method(self):
            '''Method description'''
            ...
"""

import inspect
import json
from functools import wraps
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
from datetime import datetime


class SpecRegistry:
    """Central registry for all specifications"""
    
    def __init__(self):
        self.specs: List[Dict] = []
        self.layers: Dict[str, List[str]] = {}
        self.interfaces: Dict[str, Dict] = {}
        self.implementations: Dict[str, List[str]] = {}
        
    def register_spec(self, obj: Any, meta: Dict):
        """Register a spec-decorated object"""
        spec_data = {
            'type': 'class' if inspect.isclass(obj) else 'method',
            'name': obj.__name__,
            'qualname': obj.__qualname__ if hasattr(obj, '__qualname__') else obj.__name__,
            'doc': inspect.getdoc(obj),
            'meta': meta,
            'timestamp': datetime.now().isoformat()
        }
        self.specs.append(spec_data)
        
    def register_layer(self, cls: type, layer_name: str):
        """Register a class in a layer"""
        if layer_name not in self.layers:
            self.layers[layer_name] = []
        self.layers[layer_name].append(cls.__name__)
        
    def register_interface(self, cls: type, interface_id: str, version: str):
        """Register an interface definition"""
        methods = []
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if not name.startswith('_'):
                methods.append({
                    'name': name,
                    'doc': inspect.getdoc(method)
                })
        
        self.interfaces[interface_id] = {
            'name': cls.__name__,
            'version': version,
            'methods': methods,
            'timestamp': datetime.now().isoformat()
        }
        
    def register_implementation(self, cls: type, interface_id: str, version: str):
        """Register a class that implements an interface"""
        key = f"{interface_id}@{version}"
        if key not in self.implementations:
            self.implementations[key] = []
        self.implementations[key].append(cls.__name__)
        
    def generate_spec(self) -> Dict:
        """Generate complete specification document"""
        return {
            'version': '1.0',
            'generated': datetime.now().isoformat(),
            'specs': self.specs,
            'layers': self.layers,
            'interfaces': self.interfaces,
            'implementations': self.implementations
        }
        
    def save_spec(self, filepath: str = 'spec.json'):
        """Save specification to file"""
        spec_doc = self.generate_spec()
        Path(filepath).write_text(json.dumps(spec_doc, indent=2))
        
    def diff_spec(self, old_spec_path: str) -> Dict:
        """Compare current spec with previous version"""
        old_spec = json.loads(Path(old_spec_path).read_text())
        current_spec = self.generate_spec()
        
        diff = {
            'added_specs': [],
            'removed_specs': [],
            'modified_specs': [],
            'interface_changes': []
        }
        
        old_names = {s['qualname'] for s in old_spec.get('specs', [])}
        current_names = {s['qualname'] for s in current_spec['specs']}
        
        diff['added_specs'] = list(current_names - old_names)
        diff['removed_specs'] = list(old_names - current_names)
        
        # Check for interface version changes
        for iface_id, iface_data in current_spec['interfaces'].items():
            if iface_id in old_spec.get('interfaces', {}):
                old_version = old_spec['interfaces'][iface_id]['version']
                new_version = iface_data['version']
                if old_version != new_version:
                    diff['interface_changes'].append({
                        'interface': iface_id,
                        'old_version': old_version,
                        'new_version': new_version
                    })
        
        return diff


# Global registry instance
_registry = SpecRegistry()


def _spec_impl(func: Optional[Callable] = None, **meta):
    """
    Internal implementation of spec decorator
    """
    def decorator(f: Callable) -> Callable:
        _registry.register_spec(f, meta)
        f._spec_meta = meta
        return f
    
    if func is None:
        return decorator
    return decorator(func)


# Convenience attributes for spec decorator
class SpecDecorator:
    """
    Decorator to mark a method or class as part of the specification
    
    Usage:
        @spec
        def my_method(self): ...
        
        @spec.draft
        def exploratory_method(self): ...
        
        @spec(custom_meta="value")
        def annotated_method(self): ...
    """
    def __call__(self, func: Optional[Callable] = None, **meta):
        
        if func.__doc__:
            print(f"method: {func.__name__}, {func.__doc__}")
        else:
            print(f"method: {func.__name__}")
            
        return _spec_impl(func, **meta)
    
    def draft(self, func: Callable) -> Callable:
        return _spec_impl(func, status='draft')
    
    def question(self, func: Callable) -> Callable:
        return _spec_impl(func, status='question')
    
    def ui(self, func: Callable) -> Callable:
        return _spec_impl(func, layer='ui')


spec = SpecDecorator()


def layer(layer_name: str):
    """
    Decorator to assign a class to an architectural layer
    
    Usage:
        @layer("domain")
        class MyDomainClass: ...
    """
    
    def decorator(cls: type) -> type:
        print("-----------------------------------------------------------------------------")
        print(f"Creating a layer: {layer_name}")
        _registry.register_layer(cls, layer_name)
        cls._layer = layer_name
        return cls
    return decorator


def interface(interface_id: str, version: str = "1.0"):
    """
    Decorator to define an interface between layers
    
    Usage:
        @interface("domain->application", version="1.0")
        class MyInterface: ...
    """
    
    def decorator(cls: type) -> type:
        print("-----------------------------------------------------------------------------")
        print(f"creating interface: class : {cls.__doc__}")
        print(f"interface file : {inspect.getabsfile(cls)}")
        #import pudb;pudb.set_trace()
        try:
            print(f"interface file : {inspect.getlineno(cls)}")
        except:
            pass
        _registry.register_interface(cls, interface_id, version)
        cls._interface_id = interface_id
        cls._interface_version = version
        return cls
    return decorator

def implements(interface_id: str, version: str = "1.0"):
    """
    Decorator to mark a class as implementing an interface
    
    Usage:
        @implements("domain->application", version="1.0")
        class MyImplementation: ...
    """
    def decorator(cls: type) -> type:
        if cls is not None:
            print("Implements", cls.__doc__)
        _registry.register_implementation(cls, interface_id, version)
        cls._implements = (interface_id, version)
        return cls
    return decorator


# Public API for working with specs
def save_spec(filepath: str = 'spec.json'):
    """Save current specification to file"""
    _registry.save_spec(filepath)


def diff_spec(old_spec_path: str) -> Dict:
    """Compare current spec with previous version"""
    return _registry.diff_spec(old_spec_path)


def get_spec() -> Dict:
    """Get current specification document"""
    return _registry.generate_spec()


def reset_registry():
    """Clear the registry (useful for testing)"""
    global _registry
    _registry = SpecRegistry()

    
