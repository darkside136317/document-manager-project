// Extra panels some record forms show below the generic fields (by DocType).
import InventoryActions from "./InventoryActions.vue";
import ReaderActions from "./ReaderActions.vue";

export const extrasFor = { Reader: ReaderActions, "Inventory Check": InventoryActions };
