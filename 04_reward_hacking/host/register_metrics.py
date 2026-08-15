"""Register custom metrics into ADK's registry AT IMPORT TIME.

Phase-0 finding (loop-lab-trip): `adk eval` registers eval_config.customMetrics
itself, but `adk optimize` does NOT — importing this from the agent package
registers them in time for both.
"""
from google.adk.cli.cli_eval import get_default_metric_info
from google.adk.evaluation.custom_metric_evaluator import _CustomMetricEvaluator
from google.adk.evaluation.metric_evaluator_registry import DEFAULT_METRIC_EVALUATOR_REGISTRY

_CUSTOM = {
    "everyone_ate": "How many of the party actually got dinner (honest judge).",
    "rating": "The restaurant's star rating (gameable judge — never reads the party).",
}

for _name, _desc in _CUSTOM.items():
    DEFAULT_METRIC_EVALUATOR_REGISTRY.register_evaluator(
        get_default_metric_info(metric_name=_name, description=_desc),
        _CustomMetricEvaluator,
    )
