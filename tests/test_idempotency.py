import pytest
import os
from libspec.spec import Spec

class MyIdempotentSpec(Spec):
    def modules(self):
        return []

def test_xml_generation_idempotent(tmp_path):
    spec_runner = MyIdempotentSpec()
    
    # 1. Verify `generate_xml` does not contain the timestamp
    xml_content = spec_runner.generate_xml()
    assert "date-created=" not in xml_content, "generate_xml should not emit a timestamp for idempotency"
    
    # 2. Verify `write_xml` injects the timestamp and maps to the same filename
    output_dir = tmp_path / "specs"
    
    path1 = spec_runner.write_xml(str(output_dir))
    
    # The written file should contain the timestamp
    with open(path1, "r") as f:
        written_content = f.read()
    assert "date-created=" in written_content, "write_xml should inject the timestamp temporarily before saving"
    
    # Run again, which will generate a new timestamp under the hood
    path2 = spec_runner.write_xml(str(output_dir))
    
    # The paths should be exactly identical
    assert path1 == path2, "identical specifications should generate the same filename hash"
    
    # There should only be one XML file in the output directory
    files = list(output_dir.glob("spec-*.xml"))
    assert len(files) == 1, "There should be no duplicate specs generated"

def test_consecutive_spec_generation_identical_filenames(tmp_path):
    import time
    spec_runner = MyIdempotentSpec()
    output_dir = tmp_path / "specs"

    # Generate first spec
    path1 = spec_runner.write_xml(str(output_dir))

    # Sleep briefly to guarantee datetime.now() has advanced
    time.sleep(0.01)

    # Generate second spec
    path2 = spec_runner.write_xml(str(output_dir))

    # The filenames must be completely identical
    assert os.path.basename(path1) == os.path.basename(path2), "Two specs generated consecutively with identical content must map to perfectly identical filenames."
