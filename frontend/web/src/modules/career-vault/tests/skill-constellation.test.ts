import { describe, expect, it } from "vitest";

import { resolveSkillPreviewPosition } from "../components/skill-constellation";

function horizontalRect(left: number, width: number) {
  return { left, right: left + width, width };
}

describe("resolveSkillPreviewPosition", () => {
  it("uses a side preview only when that side can contain the full preview", () => {
    expect(
      resolveSkillPreviewPosition(
        horizontalRect(200, 720),
        horizontalRect(220, 120),
      ),
    ).toEqual({ placement: "right", width: 344 });

    expect(
      resolveSkillPreviewPosition(
        horizontalRect(200, 720),
        horizontalRect(760, 120),
      ),
    ).toEqual({ placement: "left", width: 344 });
  });

  it("keeps a constrained panel preview below its anchor instead of crossing the rail", () => {
    expect(
      resolveSkillPreviewPosition(
        horizontalRect(420, 400),
        horizontalRect(440, 120),
      ),
    ).toEqual({ placement: "bottom-start", width: 344 });

    expect(
      resolveSkillPreviewPosition(
        horizontalRect(420, 400),
        horizontalRect(680, 120),
      ),
    ).toEqual({ placement: "bottom-end", width: 344 });
  });

  it("shrinks the below preview to the available panel width on narrow screens", () => {
    expect(
      resolveSkillPreviewPosition(
        horizontalRect(16, 280),
        horizontalRect(28, 96),
      ),
    ).toEqual({ placement: "bottom-start", width: 248 });
  });
});
