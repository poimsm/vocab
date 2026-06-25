export function formatDate(isoString: string): string {
    return new Date(isoString).toLocaleString("es-CL", {
        dateStyle: "medium",
        timeStyle: "short",
    });
}

export function escapeHtml(str: string): string {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}