from __future__ import annotations

from app.api.services.aws_service import AWSAPISettings, submit_graph_run_task


def _settings() -> AWSAPISettings:
    return AWSAPISettings(
        aws_region="eu-west-1",
        aws_profile=None,
        s3_input_uri="s3://bucket/inputs/",
        s3_output_uri="s3://bucket/runs/",
        ecs_cluster="cluster",
        ecs_task_definition="taskdef",
        subnet_ids=("subnet-a", "subnet-b"),
        security_group_ids=("sg-a",),
    )


class _FakeECSClient:
    def __init__(self) -> None:
        self.last_kwargs = None

    def run_task(self, **kwargs):
        self.last_kwargs = kwargs
        return {"tasks": [{"taskArn": "arn:aws:ecs:region:acct:task/cluster/task-id"}], "failures": []}


def test_rf20_aws_service_submit_graph_run_task_uses_only_operational_env() -> None:
    client = _FakeECSClient()

    task_arn = submit_graph_run_task(
        run_id="run-001",
        process_scope="p2p",
        process_family="p2p",
        dataset_input_zip="datasets/p2p/ds-001/erp_fraud_data.zip",
        llm_mode="real",
        kb_index_enabled=False,
        settings=_settings(),
        ecs_client=client,
    )

    assert task_arn.endswith("task-id")
    overrides = client.last_kwargs["overrides"]["containerOverrides"][0]
    assert overrides["command"] == [
        "run",
        "--input-zip",
        "datasets/p2p/ds-001/erp_fraud_data.zip",
        "--run-id",
        "run-001",
        "--pipeline-mode",
        "graph",
        "--process-family",
        "p2p",
        "--llm-mode",
        "real",
    ]
    assert overrides["environment"] == [
        {"name": "RUN_MODE", "value": "cloud"},
        {"name": "PROCESS_SCOPE", "value": "p2p"},
    ]
    sensitive_names = {
        "OPENAI_API_KEY",
        "LANGSMITH_API_KEY",
        "LANGSMITH_PROJECT",
        "LANGSMITH_ENDPOINT",
        "LANGSMITH_TRACING",
        "LANGCHAIN_TRACING_V2",
    }
    assert sensitive_names.isdisjoint({item["name"] for item in overrides["environment"]})


def test_rf20_aws_service_submit_graph_run_task_preserves_kb_flag() -> None:
    client = _FakeECSClient()

    submit_graph_run_task(
        run_id="run-002",
        process_scope="o2c",
        process_family="o2c",
        dataset_input_zip="datasets/o2c/ds-001/erp_fraud_data.zip",
        llm_mode="stub",
        kb_index_enabled=True,
        settings=_settings(),
        ecs_client=client,
    )

    command = client.last_kwargs["overrides"]["containerOverrides"][0]["command"]
    assert command[-1] == "--kb-index-enabled"
    assert "--llm-mode" in command
    assert "stub" in command
    assert "--process-family" in command
    assert "o2c" in command
