/** Component behaviour that DESIGN makes a rule of (roles, words, hatch, honesty of ranges). */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  AlertBannerP2,
  AlertStripP3,
  AlertTakeoverP1,
  ChecklistItem,
  formatClock,
  formatDuration,
  formatRange,
  LargeToggle,
  PinPad,
  RangeBar,
  Reach,
  SegmentedControl,
  StatusRail,
  TimeSplit,
} from "./index";

describe("formats (DESIGN §3 numerals)", () => {
  it("writes durations, ranges and the clock the same in every script", () => {
    expect(formatDuration(65)).toBe("1 h 05 m");
    expect(formatDuration(55)).toBe("55 m");
    expect(formatRange(55, 85)).toBe("55 m – 1 h 25 m");
    expect(formatClock("2026-09-24T05:12:00Z", "Asia/Kolkata")).toBe("10:42");
  });
});

describe("Reach", () => {
  it("draws the hatch only when someone is inside the swing radius", () => {
    const { container, rerender } = render(<Reach tier="danger" bearing={90} label="danger" />);
    expect(container.querySelector('path[fill^="url(#"]')).toBeNull();
    rerender(<Reach tier="critical" bearing={180} label="critical" />);
    expect(container.querySelector('path[fill^="url(#"]')).not.toBeNull();
  });

  it("is announced in words and says so when it cannot sense", () => {
    const { container } = render(<Reach tier="clear" noSensing label="No sensing on this machine" />);
    expect(screen.getByRole("img", { name: "No sensing on this machine" })).toBeInTheDocument();
    expect(container.querySelectorAll("circle[stroke-dasharray]").length).toBe(1); // dashed only
  });
});

describe("RangeBar", () => {
  it("reads as a sentence and never invents a number", () => {
    const label = "Likely 1 hour 5 minutes, between 55 minutes and 1 hour 25 minutes";
    const { rerender } = render(<RangeBar likely={65} low={55} high={85} label={label} />);
    expect(screen.getByRole("img", { name: label })).toHaveTextContent("~1 h 05 m");
    rerender(<RangeBar confidence="unknown" label="x" unknownText="Not enough data yet" />);
    expect(screen.getByText("Not enough data yet")).toBeInTheDocument();
    expect(screen.queryByText(/~/)).toBeNull();
  });
});

describe("alerts", () => {
  it("P1 is an alertdialog with one action and no dismiss", () => {
    const ack = vi.fn();
    render(
      <AlertTakeoverP1 command="Stop." situation="Person inside the swing zone"
        instruction="Stop all movement now." cause={null} ackLabel="I've stopped" onAck={ack} inline />,
    );
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveAccessibleName("Stop. Person inside the swing zone");
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    fireEvent.click(buttons[0]!);
    expect(ack).toHaveBeenCalledOnce();
  });

  it("P2 is an alert, P3 a status", () => {
    render(
      <>
        <AlertBannerP2 situation="Person close on your left. Slow down." seenLabel="Seen" onSeen={() => {}} inline />
        <AlertStripP3 text="Water break due at 11:00." inline />
      </>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Slow down");
    expect(screen.getByRole("status")).toHaveTextContent("Water break");
  });
});

describe("StatusRail", () => {
  it("shows proximity, risk, belt, sync and clock with words and labels", () => {
    render(
      <StatusRail
        mode="paused"
        proximity={{ tier: "clear", word: "Clear", label: "Proximity: clear" }}
        risk={{ band: "amber", word: "Risk raised", reason: "Heat", label: "Risk raised, mainly heat" }}
        belt={{ fastened: true, word: "Belt on" }}
        machine={{ id: "EXC001", state: "idle", word: "Idle" }}
        queue={{ priority: "P2", count: 1, label: "One more alert waiting: warning" }}
        sync={{ state: "synced", label: "Synced at 10:42" }}
        clock="10:42"
      />,
    );
    for (const name of ["Proximity: clear", "Risk raised, mainly heat", "Synced at 10:42", "One more alert waiting: warning"]) {
      expect(screen.getByRole("img", { name })).toBeInTheDocument();
    }
    expect(screen.getByText("EXC001")).toBeInTheDocument();
    expect(screen.getByText("10:42")).toBeInTheDocument();
  });
});

describe("controls", () => {
  it("PIN pad sends digits and backspace", () => {
    const digit = vi.fn();
    const back = vi.fn();
    render(<PinPad entered={1} onDigit={digit} onBackspace={back} label="1 of 4" backspaceLabel="Delete" />);
    fireEvent.click(screen.getByRole("button", { name: "7" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(digit).toHaveBeenCalledWith("7");
    expect(back).toHaveBeenCalledOnce();
  });

  it("toggle writes its state, segmented control uses aria-pressed", () => {
    const change = vi.fn();
    render(
      <>
        <LargeToggle on label="Read alerts aloud" onText="ON" offText="OFF" onChange={change} />
        <SegmentedControl label="Language" value="ta" onChange={change}
          options={[{ value: "en", label: "EN" }, { value: "ta", label: "த", lang: "ta" }]} />
      </>,
    );
    expect(screen.getByRole("switch")).toHaveTextContent("ON");
    expect(screen.getByRole("button", { name: "த" })).toHaveAttribute("aria-pressed", "true");
  });

  it("checklist has two explicit answers", () => {
    const answer = vi.fn();
    render(<ChecklistItem text="Tracks and tyres" answer={null} onAnswer={answer} okLabel="OK" problemLabel="Problem" />);
    fireEvent.click(screen.getByRole("button", { name: "Problem" }));
    expect(answer).toHaveBeenCalledWith("problem");
  });
});

describe("TimeSplit", () => {
  it("has a summary and a table for screen readers", () => {
    render(
      <TimeSplit
        segments={[{ kind: "WORKING", minutes: 310 }, { kind: "WAITING_FOR_TRUCK", minutes: 20 }]}
        axis={["07:00", "13:00"]}
        summary="Working 5 h 10 m, idle 20 m"
        names={{ WORKING: "Working", OFF: "Engine off", WAITING_FOR_TRUCK: "Waiting for a truck",
          WARM_UP: "Warm-up", SCHEDULED_BREAK: "Break", UNATTENDED_RUNNING: "Engine on, cab empty",
          HABIT: "Short stops", UNKNOWN: "Not sure" }}
      />,
    );
    expect(screen.getByText("Working 5 h 10 m, idle 20 m")).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveTextContent("Waiting for a truck20 m");
  });
});
