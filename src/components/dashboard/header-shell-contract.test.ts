import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const headerSource = readFileSync(new URL("./header.tsx", import.meta.url), "utf8");
const notificationSource = readFileSync(new URL("./notification-provider.tsx", import.meta.url), "utf8");
const layoutSource = readFileSync(new URL("../../app/dashboard/layout.tsx", import.meta.url), "utf8");

test("header route launcher no longer ships mock resource search entries", () => {
    assert.ok(headerSource.includes("Route Launcher"));
    assert.ok(!headerSource.includes("Mock resources"));
    assert.ok(!headerSource.includes("prod-web-server-01"));
    assert.ok(!headerSource.includes("main-postgres-db"));
});

test("header shell exposes real dashboard destinations and route-aware page context", () => {
    assert.ok(headerSource.includes('pageTitle: "Portfolio Command Center"'));
    assert.ok(headerSource.includes('pageTitle: "Resource Inventory"'));
    assert.ok(headerSource.includes('pageTitle: "Budget Copilot"'));
    assert.ok(headerSource.includes('pageTitle: "Architecture Workspace"'));
    assert.ok(headerSource.includes("Jump to a dashboard view"));
    assert.ok(headerSource.includes("const pathname = usePathname();"));
    assert.ok(headerSource.includes("const activeRoute = getActiveRoute(pathname);"));
    assert.ok(headerSource.includes("isPathActive(pathname, route.matchPrefixes ?? [route.href])"));
    assert.ok(headerSource.includes("{pageMeta.pageTitle}"));
    assert.ok(headerSource.includes("{pageMeta.section}"));
    assert.ok(headerSource.includes("onClick={() => handleSearchSelect(item.href)}"));
    assert.ok(headerSource.includes("router.push(href);"));
});

test("header notification control uses the live provider and preserves notification actions", () => {
    assert.ok(layoutSource.includes("<NotificationProvider>"));
    assert.ok(layoutSource.includes("<Header />"));
    assert.ok(headerSource.includes('from "@/components/dashboard/notification-provider"'));
    assert.ok(headerSource.includes("const { notifications, unreadCount, markAllRead, markAsRead, deleteNotification } = useNotifications();"));
    assert.ok(notificationSource.includes('fetch("/api/notifications")'));
    assert.ok(headerSource.includes('aria-label="View notifications"'));
    assert.ok(headerSource.includes("onClick={() => setShowNotifications((current) => !current)}"));
    assert.ok(headerSource.includes("{showNotifications ? ("));
    assert.ok(headerSource.includes("{unreadCount > 0 ? ("));
    assert.ok(headerSource.includes("notifications.map((notification) =>"));
    assert.ok(headerSource.includes("onClick={() => void markAllRead()}"));
    assert.ok(headerSource.includes("onClick={() => void markAsRead(notification.id)}"));
    assert.ok(headerSource.includes("onClick={() => void deleteNotification(notification.id)}"));
    assert.ok(headerSource.includes("No notifications right now"));
    assert.ok(headerSource.includes("View all recommendations"));
    assert.match(headerSource, /setShowNotifications\(false\);\s+router\.push\("\/dashboard\/pending-actions"\);/);
});

test("header retains the Clerk user account control", () => {
    assert.ok(headerSource.includes('import { UserButton } from "@clerk/nextjs";'));
    assert.ok(headerSource.includes("<ClientOnlyUserButton />"));
    assert.ok(headerSource.includes("<UserButton"));
});

test("header shell defines a fallback workspace context and keyboard shortcut affordance", () => {
    assert.ok(headerSource.includes("const DEFAULT_ROUTE_META ="));
    assert.ok(headerSource.includes('pageTitle: "CloudFinOps Workspace"'));
    assert.ok(headerSource.includes("const pageMeta = activeRoute ?? DEFAULT_ROUTE_META;"));
    assert.ok(headerSource.includes('if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k")'));
    assert.ok(headerSource.includes("Ctrl/⌘ K"));
});
