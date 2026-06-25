<script setup lang="ts">
import { ref, watch, onUnmounted } from "vue";
import { storeToRefs } from "pinia";
import { useToastStore } from "@/stores/toast";

interface Props {
    id?: string;
}

withDefaults(defineProps<Props>(), {
    id: "toast",
});

const toastStore = useToastStore();
const { toast } = storeToRefs(toastStore);

const toastElem = ref<HTMLDivElement | null>(null);

const icons: Record<string, string> = {
    "": "solar:check-circle-bold",
    error: "solar:close-circle-bold",
    fav: "solar:star-bold",
    learn: "solar:check-circle-bold",
};

let timeout: ReturnType<typeof setTimeout>;

watch(toast, (data) => {
    if (!data || !toastElem.value) return;

    toastElem.value.innerHTML = `
    <iconify-icon icon="${icons[data.type ?? ""] || icons[""]}"></iconify-icon>
    ${data.msg}
  `;

    toastElem.value.className = `toast show ${data.type ?? ""}`;

    clearTimeout(timeout);

    timeout = setTimeout(() => {
        toastElem.value?.classList.remove("show");
    }, 2800);
});

onUnmounted(() => {
    clearTimeout(timeout);
});
</script>