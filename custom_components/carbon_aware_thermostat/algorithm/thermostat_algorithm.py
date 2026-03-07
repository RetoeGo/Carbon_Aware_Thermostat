from dataclasses import dataclass


@dataclass
class AlgorithmInputs:
    indoor_temp: float
    target_temp: float
    outdoor_temp: float
    carbon_intensity_forecast: list[float]
    comfort_band: float


@dataclass
class AlgorithmResult:
    should_heat: bool
    recommended_target_temp: float
    reason: str


def decide_heating_action(inputs: AlgorithmInputs) -> AlgorithmResult:
    if not inputs.carbon_intensity_forecast:
        return AlgorithmResult(
            should_heat=True,
            recommended_target_temp=inputs.target_temp,
            reason="no_carbon_forecast",
        )

    lower_bound = inputs.target_temp - inputs.comfort_band
    current_ci = inputs.carbon_intensity_forecast[0]
    future_ci = inputs.carbon_intensity_forecast[1:]

    if inputs.indoor_temp <= lower_bound:
        return AlgorithmResult(
            should_heat=True,
            recommended_target_temp=inputs.target_temp,
            reason="comfort_limit_reached",
        )

    if not future_ci:
        return AlgorithmResult(
            should_heat=True,
            recommended_target_temp=inputs.target_temp,
            reason="no_future_forecast",
        )

    if current_ci <= min(future_ci):
        return AlgorithmResult(
            should_heat=True,
            recommended_target_temp=inputs.target_temp,
            reason="cleanest_period_is_now",
        )

    return AlgorithmResult(
        should_heat=False,
        recommended_target_temp=lower_bound,
        reason="waiting_for_cleaner_period",
    )
