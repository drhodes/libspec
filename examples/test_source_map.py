from libspec.spec import Feature, LeafMethods, Ctx

class TestFeature(Feature):
    """
    Test Feature
    Name: {{feature_name}}
    """
    def feature_name(self):
        return "SourceMapTest"

    def date(self):
        return "2024-01-01"
        
    def description(self):
        return "Testing source maps"

print("--- Rendering TestFeature ---")
print(TestFeature().render_xml())

class TemplateBase(Ctx, LeafMethods):
    """
    Leaf Methods Test
    {% for method in methods %}
    Method: {{method.name}}
    Source: {{method.source_ref.file}}:{{method.source_ref.start_line}}
    {% endfor %}
    """

class MyLeaf(TemplateBase):
    def my_method(self):
        """Docstring for my_method"""
        return "result"

print("\n--- Rendering MyLeaf ---")
print(MyLeaf().render_xml())
