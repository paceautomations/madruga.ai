import { defineRouteMiddleware } from '@astrojs/starlight/route-data';

/**
 * Route middleware that filters the sidebar to show only the current platform.
 *
 * The global sidebar contains all platforms as top-level groups.
 * This middleware detects which platform the current URL belongs to
 * and replaces the sidebar with only that platform's entries (unwrapped).
 */
export const onRequest = defineRouteMiddleware((context) => {
	const route = context.locals.starlightRoute;
	const pathname = context.url.pathname;

	// Extract platform slug from URL: /fulano/... → "fulano"
	const match = pathname.match(/^\/([^/]+)\//);
	if (!match) return;
	const currentPlatform = match[1];

	// Find the sidebar group whose links match this platform
	for (const entry of route.sidebar) {
		if (entry.type !== 'group') continue;

		const hasMatchingLink = containsLinkForPlatform(entry, currentPlatform);
		if (hasMatchingLink) {
			// Replace entire sidebar with this platform's entries (unwrapped)
			route.sidebar = entry.entries;
			return;
		}
	}
});

/** Recursively check if a sidebar group contains any link for a given platform. */
function containsLinkForPlatform(
	entry: { type: string; [key: string]: unknown },
	platform: string
): boolean {
	if (entry.type === 'link') {
		const href = (entry as { href: string }).href;
		return href.startsWith(`/${platform}/`);
	}
	if (entry.type === 'group') {
		const entries = (entry as { entries: Array<{ type: string; [key: string]: unknown }> }).entries;
		return entries.some((child) => containsLinkForPlatform(child, platform));
	}
	return false;
}
