"""Drive the G*Power GUI through the macOS Accessibility API — black-box only.

This is the instrument behind every ``[GÖZLEM]`` observation in the repository.
It does what an operator does with a mouse: pick a test and an analysis from
the pop-up menus, type numbers into the visible input fields, press
*Calculate*, and read the numbers printed in the *Output parameters* panel.
It never reads process memory, never loads the binary, and never touches a
file inside the application bundle.

Requirements: macOS, G*Power 3.1.9.x for Mac running, and Accessibility
permission for the terminal that runs this script (System Settings → Privacy
& Security → Accessibility).

Usage (one call)::

    python tools/gpower_ax.py --test "Generic t test" --analysis "Post hoc" \
        --set "Noncentrality parameter δ=0" --set "Df=30" \
        --set "α err prob=0.2" --set "Tail(s)=Two"

Labels are matched by prefix against the GUI's own label text. Numbers are
typed in the locale the GUI is running in (``--decimal ,`` for a comma
locale); outputs are returned with ``.`` as decimal separator.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

TEST_MENU = {
    "indep": "Means: Difference between two independent means (two groups)",
    "paired": "Means: Difference between two dependent means (matched pairs)",
    "one-sample": "Means: Difference from constant (one sample case)",
    "point-biserial": "Correlation: Point biserial model",
    "regression": "Linear multiple regression: Fixed model, single regression coefficient",
    "generic": "• Generic t test",
}

ANALYSIS_PREFIX = {
    "a priori": "A priori",
    "post hoc": "Post hoc",
    "criterion": "Criterion",
    "sensitivity": "Sensitivity",
    "compromise": "Compromise",
}

_SCRIPT = r'''
on findPrefix(itemsList, pfx)
	repeat with n in itemsList
		if (n as text) starts with pfx then return (n as text)
	end repeat
	error "no menu item starting with " & pfx
end findPrefix

on pickPopup(pb, pfx)
	tell application "System Events" to tell process "G*Power"
		if (value of pb as text) starts with pfx then return
		click pb
		delay 0.4
		try
			set target to my findPrefix(name of every menu item of menu 1 of pb, pfx)
		on error msg
			key code 53
			delay 0.3
			error msg
		end try
		click menu item target of menu 1 of pb
		delay 0.5
	end tell
end pickPopup

on groupWithLabel(w, lbl)
	tell application "System Events" to tell process "G*Power"
		repeat with g in (groups of w)
			try
				repeat with s in (static texts of g)
					if (value of s as text) is lbl then return g
				end repeat
			end try
		end repeat
	end tell
	error "no group " & lbl
end groupWithLabel

on setField(g, pfx, val)
	tell application "System Events" to tell process "G*Power"
		set labelY to missing value
		repeat with s in (static texts of g)
			if (value of s as text) starts with pfx then
				set labelY to item 2 of (position of s as list)
				exit repeat
			end if
		end repeat
		if labelY is missing value then error "no input label " & pfx
		repeat with tf in (text fields of g)
			set y to item 2 of (position of tf as list)
			if (y - labelY) > -12 and (y - labelY) < 12 then
				set focused of tf to true
				keystroke "a" using command down
				keystroke val
				keystroke tab
				delay 0.15
				return
			end if
		end repeat
		repeat with pb in (pop up buttons of g)
			set y to item 2 of (position of pb as list)
			if (y - labelY) > -12 and (y - labelY) < 12 then
				my pickPopup(pb, val)
				return
			end if
		end repeat
		error "no control next to label " & pfx
	end tell
end setField

on readPanel(g)
	tell application "System Events" to tell process "G*Power"
		set out to ""
		set txts to static texts of g
		repeat with s in txts
			set sv to value of s as text
			set sx to item 1 of (position of s as list)
			set sy to item 2 of (position of s as list)
			set out to out & sx & tab & sy & tab & sv & linefeed
		end repeat
		repeat with tf in (text fields of g)
			set out to out & "F" & tab & (item 2 of (position of tf as list)) & tab & (value of tf as text) & linefeed
		end repeat
		repeat with pb in (pop up buttons of g)
			set out to out & "F" & tab & (item 2 of (position of pb as list)) & tab & (value of pb as text) & linefeed
		end repeat
		return out
	end tell
end readPanel

on run
	tell application "System Events" to tell process "G*Power"
		set frontmost to true
		delay 0.2
		set w to window "G*Power 3.1"
		my pickPopup(pop up button 1 of my groupWithLabel(w, "Test family"), "t tests")
		my pickPopup(pop up button 1 of my groupWithLabel(w, "Statistical test"), "%TEST%")
		my pickPopup(pop up button 1 of my groupWithLabel(w, "Type of power analysis"), "%ANALYSIS%")
		set gi to my groupWithLabel(w, "Input parameters")
%SETS%
		click button "Calculate" of w
		delay 0.8
		set dlg to ""
		try
			if exists sheet 1 of w then
				repeat with s in (static texts of sheet 1 of w)
					set dlg to dlg & (value of s as text) & " "
				end repeat
				click button 1 of sheet 1 of w
				delay 0.3
			end if
		end try
		set nw to count of windows
		repeat with k from nw to 1 by -1
			try
				set ow to window k
				if name of ow is not "G*Power 3.1" then
					try
						set dlg to dlg & (name of ow as text) & ": "
					end try
					try
						repeat with s in (static texts of ow)
							set dlg to dlg & (value of s as text) & " "
						end repeat
					end try
					try
						set dlg to dlg & (value of text area 1 of scroll area 1 of ow as text) & " "
					end try
					click button 1 of ow
					delay 0.3
				end if
			end try
		end repeat
		set go to my groupWithLabel(w, "Output parameters")
		return "##DLG" & dlg & linefeed & "##IN" & linefeed & my readPanel(gi) & "##OUT" & linefeed & my readPanel(go)
	end tell
end run
'''


def _as_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _parse_panel(block: str) -> dict[str, str]:
    """Pair each label with the value printed on the same row."""
    labels: list[tuple[float, str]] = []
    values: list[tuple[float, str]] = []
    for line in block.strip().splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        x, y, v = parts
        y = float(y)
        if x == "F":
            values.append((y, v))
        elif _looks_numeric(v):
            values.append((y, v))
        else:
            labels.append((y, v))
    out: dict[str, str] = {}
    for ly, lab in labels:
        if lab in ("Input parameters", "Output parameters"):
            continue
        near = [(abs(vy - ly), v) for vy, v in values if abs(vy - ly) < 12]
        if near:
            out[lab] = min(near)[1]
    return out


def _parse_output(block: str) -> dict[str, str]:
    """Output rows come back as label, value, label, value ... in reading
    order; the value element's reported position is not always its own row,
    so pair them by sequence rather than by y."""
    out: dict[str, str] = {}
    pending: str | None = None
    for line in block.strip().splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or parts[0] == "F":
            continue
        v = parts[2]
        if _looks_numeric(v):
            if pending is not None:
                out[pending] = v
                pending = None
        elif v != "Output parameters":
            pending = v
    return out


def _looks_numeric(v: str) -> bool:
    try:
        float(v.replace(",", "."))
        return True
    except ValueError:
        return False


def _normalise(v: str) -> str:
    return v.replace(",", ".") if _looks_numeric(v) else v


def run(test: str, analysis: str, settings: list[tuple[str, str]],
        decimal: str = ",") -> dict:
    test_item = TEST_MENU.get(test, test)
    analysis_item = ANALYSIS_PREFIX.get(analysis.lower(), analysis)
    lines = []
    for label, value in settings:
        if _looks_numeric(value):
            value = value.replace(".", decimal)
        lines.append(f"\t\tmy setField(gi, {_as_str(label)}, {_as_str(value)})")
    script = (_SCRIPT.replace("%TEST%", test_item.replace('"', '\\"'))
              .replace("%ANALYSIS%", analysis_item)
              .replace("%SETS%", "\n".join(lines)))
    for _attempt in range(3):
        proc = subprocess.run(["osascript", "-"], input=script, text=True,
                              capture_output=True, timeout=60)
        if proc.returncode == 0:
            break
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    raw = proc.stdout
    dlg, rest = raw.split("##IN", 1)
    dialog = dlg.replace("##DLG", "").strip()
    inp, outp = rest.split("##OUT", 1)
    return {
        "test": test_item,
        "analysis": analysis_item,
        "inputs": {k: _normalise(v) for k, v in _parse_panel(inp).items()},
        "outputs": {k: _normalise(v) for k, v in _parse_output(outp).items()},
        "dialog": dialog or None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--test", required=True)
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--set", action="append", default=[], metavar="LABEL=VALUE")
    ap.add_argument("--decimal", default=",")
    a = ap.parse_args(argv)
    settings = [tuple(s.split("=", 1)) for s in a.set]
    print(json.dumps(run(a.test, a.analysis, settings, a.decimal),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
