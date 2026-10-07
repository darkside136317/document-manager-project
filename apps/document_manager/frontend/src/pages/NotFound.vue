<script setup>
import EmptyState from "../components/EmptyState.vue";
</script>

<template>
  <EmptyState icon="alert-triangle" title="Không tìm thấy trang" text="Địa chỉ này không tồn tại hoặc bạn không có quyền truy cập.">
    <RouterLink class="btn btn-primary no-underline" to="/">Về trang Tổng quan</RouterLink>
  </EmptyState>
</template>
