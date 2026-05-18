"use client";

import type { ForecastViewProps } from "@/components/dashboard/forecast-view";
import { ForecastView } from "@/components/dashboard/forecast-view";

export function ForecastViewClient(props: ForecastViewProps) {
    return <ForecastView {...props} />;
}
