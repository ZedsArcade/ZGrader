import { toast } from "@heroui/react";

export function toastSuccess(message: string) {
  toast.success(message);
}

export function toastError(message: string) {
  toast.danger(message);
}
