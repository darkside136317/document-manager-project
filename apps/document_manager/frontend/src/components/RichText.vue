<script setup>
import { onMounted, ref, watch } from "vue";
import Icon from "./Icon.vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
  inputId: { type: String, default: undefined },
});
const emit = defineEmits(["update:modelValue"]);
const surface = ref(null);

// Small, dependency-free editor for descriptions. The server sanitises the HTML on save.
const commands = [
  { cmd: "bold", label: "B", title: "Đậm", cls: "font-bold" },
  { cmd: "italic", label: "I", title: "Nghiêng", cls: "italic" },
  { cmd: "underline", label: "U", title: "Gạch chân", cls: "underline" },
  { cmd: "insertUnorderedList", label: "•", title: "Danh sách chấm" },
  { cmd: "insertOrderedList", label: "1.", title: "Danh sách số" },
];

function sync() {
  if (surface.value && surface.value.innerHTML !== (props.modelValue || "")) {
    surface.value.innerHTML = props.modelValue || "";
  }
}
onMounted(sync);
watch(() => props.modelValue, sync);

function onInput() {
  const html = surface.value.innerHTML;
  emit("update:modelValue", html === "<br>" ? "" : html);
}
function run(cmd) {
  if (props.disabled) return;
  surface.value.focus();
  document.execCommand(cmd, false, null);
  onInput();
}
function link() {
  if (props.disabled) return;
  const url = window.prompt("Địa chỉ liên kết (https://...)");
  if (url && /^(https?:|mailto:)/i.test(url)) run_with("createLink", url);
}
function run_with(cmd, value) {
  surface.value.focus();
  document.execCommand(cmd, false, value);
  onInput();
}
</script>

<template>
  <div class="rounded-md border border-line-strong bg-surface" :class="{ 'opacity-70': disabled }">
    <div v-if="!disabled" class="flex flex-wrap gap-1 border-b border-line bg-surface-muted px-2 py-1">
      <button
        v-for="c in commands"
        :key="c.cmd"
        type="button"
        class="btn btn-ghost !min-h-0 !px-2 !py-1 text-sm"
        :class="c.cls"
        :title="c.title"
        :aria-label="c.title"
        @mousedown.prevent="run(c.cmd)"
      >{{ c.label }}</button>
      <button type="button" class="btn btn-ghost !min-h-0 !px-2 !py-1 text-sm" title="Chèn liên kết" aria-label="Chèn liên kết" @mousedown.prevent="link">
        <Icon name="external-link" :size="14" />
      </button>
    </div>
    <div
      :id="inputId"
      ref="surface"
      class="rich-surface px-3 py-2 text-sm outline-none"
      :contenteditable="!disabled"
      role="textbox"
      aria-multiline="true"
      data-placeholder="Nhập nội dung..."
      @input="onInput"
    ></div>
  </div>
</template>
