export type UserFeatureMeta = {
    feature: string;
    enabled: boolean;
    last_used?: string | null;
    first_upload_at?: string | null;
};

type UserFeaturesResponse = {
    features?: string[];
    feature_details?: Record<string, UserFeatureMeta>;
};

export async function getUserFeaturesResponse(): Promise<{
    features: string[];
    featureDetails: Record<string, UserFeatureMeta>;
}> {
    try {
        const response = await fetch("/api/user/features", {
            cache: "no-store",
        });
        if (!response.ok) {
            return { features: [], featureDetails: {} };
        }

        const payload = (await response.json()) as UserFeaturesResponse;
        return {
            features: Array.isArray(payload.features) ? payload.features : [],
            featureDetails: payload.feature_details || {},
        };
    } catch {
        return { features: [], featureDetails: {} };
    }
}

export async function getUserFeatures(): Promise<string[]> {
    const { features } = await getUserFeaturesResponse();
    return features;
}

export async function hasFeature(feature: string): Promise<boolean> {
    const features = await getUserFeatures();
    return features.includes(feature);
}
