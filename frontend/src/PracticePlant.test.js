import { render, screen } from "@testing-library/react";
import PracticePlant from "./PracticePlant";

test("grows a small SVG plant with completed interviews", () => {
  const { container, rerender } = render(<PracticePlant completed={0} />);
  expect(screen.getByRole("img", { name: /0 completed interviews/ }).tagName.toLowerCase()).toBe("svg");
  expect(container.querySelectorAll(".practice-plant-leaf")).toHaveLength(0);

  rerender(<PracticePlant completed={4} celebrate />);
  expect(container.querySelectorAll(".practice-plant-leaf")).toHaveLength(4);
  expect(container.querySelectorAll(".practice-plant-leaf.is-new")).toHaveLength(1);

  rerender(<PracticePlant completed={12} />);
  expect(container.querySelectorAll(".practice-plant-leaf")).toHaveLength(12);
});
