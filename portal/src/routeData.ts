import { defineRouteMiddleware } from '@astrojs/starlight/route-data';
// @ts-expect-error — neighbour .mjs module, no .d.ts emitted.
import { isScreenFlowEnabled } from './lib/platforms.mjs';

/**
 * Route middleware that filters the sidebar to show only the current platform.
 *
 * The global sidebar contains all platforms as top-level groups.
 * This middleware detects which platform the current URL belongs to
 * and replaces the sidebar with only that platform's entries (unwrapped).
 *
 * Epic 027 — T034: when the current platform opted into screen-flow
 * (`platform.yaml: screen_flow.enabled === true`) we splice a "Screens"
 * link into the unwrapped sidebar pointing to `/<platform>/screens/`
 * (matches the SSG route emitted by `pages/[platform]/screens.astro`).
 * Plataformas opted-out NÃO recebem a entry — opt-out invisível
 * (FR-016, US-03 cenário 3).
 */
export const onRequest = defineRouteMiddleware((context) => {
	const route = context.locals.starlightRoute;
	const pathname = context.url.pathname;

	// Root and 404 pages: hide sidebar (no platform context)
	if (pathname === '/' || pathname === '/404/') {
		route.sidebar = [];
		return;
	}

	// Extract platform slug from URL: /prosauai/... → "prosauai"
	const match = pathname.match(/^\/([^/]+)\//);
	if (!match) return;
	const currentPlatform = match[1];

	// Find the sidebar group whose links match this platform
	for (const entry of route.sidebar) {
		if (entry.type !== 'group') continue;

		const hasMatchingLink = containsLinkForPlatform(entry, currentPlatform);
		if (hasMatchingLink) {
			// Replace entire sidebar with this platform's entries (unwrapped)
			let entries = entry.entries;

			// FR-016: only opt-in platforms get the Screens entry. The
			// presence check runs at request time so authors flipping
			// `enabled` in platform.yaml during dev see immediate effect
			// without restarting Astro. Failures fall back to "no entry"
			// so a stat error never breaks the whole sidebar.
			if (isScreenFlowEnabledSafe(currentPlatform)) {
				entries = withScreensEntry(entries, currentPlatform, pathname);
			}

			route.sidebar = entries;
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

/**
 * Wraps `isScreenFlowEnabled` so any filesystem hiccup downgrades to a
 * silent `false` (opt-out invisível). We never want a missing manifest
 * during a hot reload to crash the entire navigation tree.
 */
function isScreenFlowEnabledSafe(platform: string): boolean {
	try {
		return isScreenFlowEnabled(platform) === true;
	} catch {
		return false;
	}
}

/**
 * Insert a "Screens" sidebar link right after Control Panel (when present)
 * so the navigation order matches the existing convention. Mutates a copy
 * — the original entries array is not touched.
 */
function withScreensEntry(
	entries: ReadonlyArray<{ type: string; [key: string]: unknown }>,
	platform: string,
	pathname: string,
): Array<{ type: string; [key: string]: unknown }> {
	const next = [...entries];
	const screensHref = `/${platform}/screens/`;
	const screens = {
		type: 'link',
		label: 'Screens',
		href: screensHref,
		isCurrent: pathname === screensHref || pathname === `/${platform}/screens`,
		attrs: {},
		badge: undefined,
	} as unknown as { type: string; [key: string]: unknown };

	const insertAt = next.findIndex(
		(e) =>
			e.type === 'link' &&
			typeof (e as { label?: string }).label === 'string' &&
			(e as { label: string }).label.toLowerCase() === 'control panel',
	);
	if (insertAt >= 0) {
		next.splice(insertAt + 1, 0, screens);
	} else {
		next.unshift(screens);
	}
	return next;
}
