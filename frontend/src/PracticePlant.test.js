/** Verify starter, added, and animated leaves without DOM implementation queries. */
import { render, screen } from "@testing-library/react";
import PracticePlant from "./PracticePlant";

test("grows a small SVG plant with completed interviews", () => {
  const { rerender } = render(<PracticePlant completed={0} />);
  expect(screen.getByRole("img", { name: /0 completed interviews/ })).toBeInTheDocument();
  expect(screen.getAllByTestId("leaf-starter")).toHaveLength(2);
  expect(screen.queryAllByTestId(/^leaf-(grown|new)$/)).toHaveLength(0);

  rerender(<PracticePlant completed={4} celebrate />);
  expect(screen.getAllByTestId(/^leaf-(grown|new)$/)).toHaveLength(4);
  expect(screen.getAllByTestId("leaf-new")).toHaveLength(1);

  rerender(<PracticePlant completed={12} />);
  expect(screen.getAllByTestId(/^leaf-(grown|new)$/)).toHaveLength(12);
});
