export interface TwitterProfile {
    name: string;
    handle: string;
    bio: string;
    avatarUrl: string | null;
    websiteUrl: string | null;
    location: string | null;
}

/**
 * Extract the Twitter handle from any twitter.com/x.com URL.
 * Works on profiles, tweets, and feeds (e.g. x.com/karpathy/status/123 -> "karpathy").
 */
export function extractTwitterHandle(url: string): string | null {
    try {
        const parsed = new URL(url);
        if (!['twitter.com', 'x.com'].includes(parsed.hostname)) return null;
        const segments = parsed.pathname.split('/').filter(Boolean);
        if (segments.length === 0) return null;
        const handle = segments[0].toLowerCase();
        if (['home', 'explore', 'search', 'notifications', 'messages', 'settings', 'i', 'compose'].includes(handle)) return null;
        return handle;
    } catch {
        return null;
    }
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

export interface TweetContent {
    text: string;
    url: string | null;
}

/**
 * Extract text and URL from a tweet DOM element.
 * Expects the element to be or contain [data-testid="tweet"].
 */
export function extractTweetContent(tweetEl: Element): TweetContent | null {
    const textEl = tweetEl.querySelector('[data-testid="tweetText"]');
    const text = textEl?.textContent?.trim() || '';
    if (!text) return null;

    // Tweet URL is in the timestamp link: <a href="/user/status/123"><time ...></a>
    const timeLink = tweetEl.querySelector('time')?.closest('a') as HTMLAnchorElement | null;
    let url: string | null = null;
    if (timeLink?.href) {
        try {
            url = new URL(timeLink.href, window.location.origin).href;
        } catch {
            url = timeLink.href;
        }
    }

    return { text, url };
}
