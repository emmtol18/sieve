export interface TwitterProfile {
    name: string;
    handle: string;
    bio: string;
    avatarUrl: string | null;
    websiteUrl: string | null;
    location: string | null;
}

export function isTwitterProfile(url: string): boolean {
    try {
        const parsed = new URL(url);
        if (!['twitter.com', 'x.com'].includes(parsed.hostname)) return false;
        const segments = parsed.pathname.split('/').filter(Boolean);
        return segments.length === 1 && !['home', 'explore', 'search', 'notifications', 'messages', 'settings', 'i'].includes(segments[0]);
    } catch {
        return false;
    }
}

export function extractTwitterProfile(): TwitterProfile | null {
    try {
        const nameEl = document.querySelector('[data-testid="UserName"] span');
        const name = nameEl?.textContent?.trim() || '';

        const handle = window.location.pathname.split('/').filter(Boolean)[0] || '';

        const bioEl = document.querySelector('[data-testid="UserDescription"]');
        const bio = bioEl?.textContent?.trim() || '';

        const avatarEl = document.querySelector('[data-testid="UserAvatar"] img') as HTMLImageElement;
        let avatarUrl = avatarEl?.src || null;
        if (avatarUrl) {
            avatarUrl = avatarUrl.replace(/_normal\.|_bigger\./, '_400x400.');
        }

        const websiteEl = document.querySelector('[data-testid="UserUrl"] a') as HTMLAnchorElement;
        const websiteUrl = websiteEl?.href || null;

        const locationEl = document.querySelector('[data-testid="UserLocation"]');
        const location = locationEl?.textContent?.trim() || null;

        if (!name && !handle) return null;
        return { name, handle, bio, avatarUrl, websiteUrl, location };
    } catch {
        return null;
    }
}
