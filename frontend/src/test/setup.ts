import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
afterEach(() => {
  cleanup();
  localStorage.clear();
});
Object.defineProperty(window, "scrollTo", { value: vi.fn(), writable: true });
HTMLDialogElement.prototype.showModal = function () {
  this.setAttribute("open", "");
};
