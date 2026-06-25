// stores/toast.ts
import { defineStore } from "pinia";

export type ToastType = "" | "error" | "fav" | "learn";

interface ToastData {
    msg: string;
    type?: ToastType;
}

export const useToastStore = defineStore("toast", {
    state: () => ({
        toast: null as ToastData | null,
    }),

    actions: {
        show(msg: string, type: ToastType = "") {
            this.toast = {
                msg,
                type,
            };
        },

        success(msg: string) {
            this.show(msg);
        },

        error(msg: string) {
            this.show(msg, "error");
        },

        fav(msg: string) {
            this.show(msg, "fav");
        },

        learn(msg: string) {
            this.show(msg, "learn");
        },

        clear() {
            this.toast = null;
        },
    },
});