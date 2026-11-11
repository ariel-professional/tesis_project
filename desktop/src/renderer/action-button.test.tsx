import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ActionButton, ActionIconButton } from "@domain-ui-kit";

describe("shared action buttons", () => {
  it("replaces a text button's action icon with an accessible busy spinner", () => {
    render(<ActionButton action="calculate" label="Calculando" loading />);

    const button = screen.getByRole("button", { name: "Calculando" });
    expect(button.getAttribute("aria-busy")).toBe("true");
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(button.querySelector(".ui-action-spinner")).not.toBeNull();
    expect(button.querySelector(".ui-action-icon")).toBeNull();
  });

  it("replaces an icon-only button's action icon without losing its label", () => {
    render(<ActionIconButton action="view-details" label="Ver detalle" loading />);

    const button = screen.getByRole("button", { name: "Ver detalle" });
    expect(button.getAttribute("aria-busy")).toBe("true");
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(button.querySelector(".ui-action-spinner")).not.toBeNull();
    expect(button.querySelector(".ui-action-icon")).toBeNull();
  });
});
