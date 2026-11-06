# SYNTHETIC 模型与规则验证

```json
{
  "synthetic": true,
  "run_profile": "full",
  "model_version": "pv-v1",
  "test_period": "2025-11-01 <= local date < 2026-01-01",
  "model_comparison": {
    "physical": {
      "n": 0,
      "mae_kw": null,
      "rmse_kw": null,
      "capacity_nmae": null
    },
    "regression": {
      "n": 0,
      "mae_kw": null,
      "rmse_kw": null,
      "capacity_nmae": null
    },
    "capacity_median": {
      "n": 0,
      "mae_kw": null,
      "rmse_kw": null,
      "capacity_nmae": null
    }
  },
  "strata": [],
  "event": {
    "tp": 0,
    "fp": 0,
    "fn": 0,
    "precision": null,
    "recall": null,
    "f1": null
  },
  "point_equipment": {
    "tp": 0,
    "fp": 0,
    "fn": 0,
    "precision": null,
    "recall": null,
    "f1": null
  },
  "fixed_threshold_point": {
    "tp": 0,
    "fp": 0,
    "fn": 0,
    "precision": null,
    "recall": null,
    "f1": null
  },
  "quality_evaluation": {
    "status": "quarantine row conservation tested; labeled quality PR not implemented"
  },
  "threshold_sensitivity_point_test_descriptive": {
    "-0.1": {
      "tp": 0,
      "fp": 0,
      "fn": 0,
      "precision": null,
      "recall": null,
      "f1": null
    },
    "-0.2": {
      "tp": 0,
      "fp": 0,
      "fn": 0,
      "precision": null,
      "recall": null,
      "f1": null
    },
    "-0.3": {
      "tp": 0,
      "fp": 0,
      "fn": 0,
      "precision": null,
      "recall": null,
      "f1": null
    }
  },
  "threshold_selection": "-0.20 demonstration preset; no claim of validation optimization",
  "precision_at_k": null,
  "k": 0,
  "false_alarms_per_station_day": null,
  "mean_delay_minutes": null,
  "mean_duration_error_minutes": null,
  "unobservable_truth_n": 0,
  "fp_examples": [],
  "fn_examples": [],
  "event_matching": "chronological prediction, nearest start among overlapping +/-10min, one-to-one",
  "limitation": "Sensor-bias truth treated as equipment candidate; no unique cause attribution. Test sensitivity is descriptive, not tuning."
}
```
