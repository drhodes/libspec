import pytest
import json
from libspec_scheduler.mcp import (
    init_scheduler_handler,
    request_task_handler,
    report_task_status_handler,
    publish_micro_patch_handler,
    get_micro_patches_handler,
    scheduler_dag_resource,
    active_workers_resource,
    patch_log_resource,
    reset_global_scheduler,
)


def test_mcp_scheduler_lifecycle():
    """Verify the end-to-end lifecycle of the scheduler via MCP handlers."""
    reset_global_scheduler()
    
    # 1. Initialize
    res = init_scheduler_handler()
    assert "initialized" in res.lower()
    
    # 2. Request task
    task_res = request_task_handler("worker_1")
    # It should assign some task or state it's empty if no specs are pending.
    # Since we have pending specs in our workspace (the scheduler itself and refactored common types),
    # it should find them and assign one of them!
    assert "assigned" in task_res.lower() or "no ready tasks" in task_res.lower()
    
    if "assigned" in task_res.lower():
        # Parse assigned task
        data = json.loads(task_res)
        ref = data["component_ref"]
        
        # 3. Report Success
        report_res = report_task_status_handler("worker_1", ref, "success")
        assert "implemented" in report_res.lower()


def test_mcp_patch_sharing():
    """Verify micro-patch publishing and polling via MCP handlers."""
    reset_global_scheduler()
    
    # Publish a patch
    pub_res = publish_micro_patch_handler(
        subagent_id="worker_1",
        file_path="libspec/common.py",
        patch_diff="--- old\n+++ new\n",
        description="test patch",
        patch_id="patch_123",
    )
    assert "published" in pub_res.lower()
    
    # Fetch patches since None
    get_res = get_micro_patches_handler(None)
    patches = json.loads(get_res)
    assert len(patches) == 1
    assert patches[0]["patch_id"] == "patch_123"
    
    # Fetch patches since patch_123
    get_res_empty = get_micro_patches_handler("patch_123")
    patches_empty = json.loads(get_res_empty)
    assert len(patches_empty) == 0


def test_mcp_resources():
    """Verify MCP resource JSON serialized listings."""
    reset_global_scheduler()
    
    init_scheduler_handler()
    
    # Check DAG resource
    dag_json = scheduler_dag_resource()
    dag_data = json.loads(dag_json)
    assert "nodes" in dag_data
    
    # Check Active Workers
    workers_json = active_workers_resource()
    workers_data = json.loads(workers_json)
    assert isinstance(workers_data, list)
    
    # Check Patch Log
    log_json = patch_log_resource()
    log_data = json.loads(log_json)
    assert isinstance(log_data, list)
