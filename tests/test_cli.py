"""The CLI contract (docs/CLI-CONTRACT.md) is a promise; these tests lock it."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from gpower_rea.cli import (
    EXIT_CONFORMANCE,
    EXIT_NO_SOLUTION,
    EXIT_OK,
    EXIT_USAGE,
    EXIT_VALIDATION,
    main,
)

ROOT = Path(__file__).resolve().parents[1]


def run(argv, capsys):
    code = main(argv)
    cap = capsys.readouterr()
    return code, cap.out, cap.err


# --------------------------------------------------------------------------
# S-1 / S-2: subcommands and the implicit `solve`
# --------------------------------------------------------------------------
def test_version(capsys):
    code, out, _ = run(["version"], capsys)
    assert code == EXIT_OK
    assert out.startswith("gpower ")


def test_version_flag(capsys):
    code, out, _ = run(["--version"], capsys)
    assert code == EXIT_OK and "gpower" in out


def test_no_arguments_prints_help(capsys):
    code, out, _ = run([], capsys)
    assert code == EXIT_USAGE
    assert "COMMAND" in out


def test_implicit_solve_subcommand(capsys):
    explicit = run(
        ["solve", "-t", "indep", "-s", "n", "-a", "0.05", "-p", "0.95",
         "-e", "0.5", "--json"],
        capsys,
    )
    implicit = run(
        ["-t", "indep", "-s", "n", "-a", "0.05", "-p", "0.95", "-e", "0.5", "--json"],
        capsys,
    )
    assert explicit[0] == implicit[0] == EXIT_OK
    assert json.loads(explicit[1]) == json.loads(implicit[1])


# --------------------------------------------------------------------------
# S-3: the JSON result schema
# --------------------------------------------------------------------------
def test_json_schema_shape(capsys):
    code, out, _ = run(
        ["solve", "--test", "ttest-indep-means", "--solve", "n",
         "--alpha", "0.05", "--power", "0.95", "--effect-size", "0.5",
         "--tails", "2", "--json"],
        capsys,
    )
    assert code == EXIT_OK
    doc = json.loads(out)
    assert doc["schema"] == "gpower-rea/result/1"
    for key in (
        "test", "test_title", "family", "solve_for", "tails", "alpha",
        "power", "df", "noncentrality", "critical_t", "effect_size",
        "sample_size", "target", "engine", "warnings",
    ):
        assert key in doc, f"missing key {key}"
    assert doc["sample_size"] == {
        "n1": 105, "n2": 105, "total": 210,
        "allocation_ratio": 1.0, "actual_ratio": 1.0,
    }
    assert doc["df"] == 208
    assert doc["power"] == pytest.approx(0.9501287, abs=1e-6)
    assert doc["effect_size"] == {"name": "d", "value": 0.5}
    assert doc["engine"]["allocation_rule"] == "even-total"


def test_canonical_example_text_output(capsys):
    code, out, _ = run(
        ["-t", "indep", "-a", "0.05", "-p", "0.95", "-e", "0.5"], capsys
    )
    assert code == EXIT_OK
    assert "Total sample size              = 210" in out
    assert "Sample size group 1            = 105" in out
    assert "a priori" in out.lower()


def test_csv_output(capsys):
    code, out, _ = run(
        ["-t", "one-sample", "-a", "0.05", "-p", "0.8", "-e", "0.5", "-f", "csv"],
        capsys,
    )
    assert code == EXIT_OK
    header, row = out.strip().splitlines()[:2]
    assert "N" in header.split(",")
    idx = header.split(",").index("N")
    assert int(row.split(",")[idx]) == 34


def test_apa_output(capsys):
    code, out, _ = run(
        ["-t", "indep", "-a", "0.05", "-p", "0.95", "-e", "0.5", "-f", "apa"],
        capsys,
    )
    assert code == EXIT_OK
    assert "n1 = 105" in out and "total N = 210" in out


# --------------------------------------------------------------------------
# All five analysis types reachable from the CLI
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "argv",
    [
        ["-t", "indep", "-s", "n", "-a", ".05", "-p", ".8", "-e", ".5"],
        ["-t", "indep", "-s", "power", "-a", ".05", "-e", ".5", "--n1", "64", "--n2", "64"],
        ["-t", "indep", "-s", "alpha", "-p", ".8", "-e", ".5", "--n1", "40", "--n2", "40"],
        ["-t", "indep", "-s", "effect-size", "-a", ".05", "-p", ".8", "--n1", "40", "--n2", "40"],
        ["-t", "indep", "-s", "compromise", "-e", ".5", "--n1", "40", "--n2", "40", "--q", "2"],
    ],
)
def test_every_solve_mode(argv, capsys):
    code, out, err = run([*argv, "--json"], capsys)
    assert code == EXIT_OK, err
    doc = json.loads(out)
    assert 0.0 < doc["alpha"] < 1.0
    assert 0.0 < doc["power"] < 1.0


def test_regression_requires_predictor_count_flag(capsys):
    code, out, _ = run(
        ["-t", "regression-coef", "-a", ".05", "-p", ".8", "-e", ".15",
         "--predictors", "5", "--json"],
        capsys,
    )
    assert code == EXIT_OK
    doc = json.loads(out)
    assert doc["effect_size"]["parameters"] == {"predictors": 5}
    assert doc["df"] == doc["sample_size"]["total"] - 6


def test_generic_test_via_param_flag(capsys):
    code, out, _ = run(
        ["-t", "generic", "-s", "power", "-a", ".05", "-e", "2.5",
         "--param", "df=30", "--json"],
        capsys,
    )
    assert code == EXIT_OK
    assert json.loads(out)["df"] == 30.0


# --------------------------------------------------------------------------
# S-5: exit codes
# --------------------------------------------------------------------------
def test_missing_test_is_usage_error(capsys):
    code, _, err = run(["solve", "-a", "0.05", "-p", "0.8", "-e", "0.5"], capsys)
    assert code == EXIT_USAGE
    assert "--test" in err


def test_unknown_test_is_validation_error(capsys):
    code, _, err = run(["-t", "anova", "-a", ".05", "-p", ".8", "-e", ".5"], capsys)
    assert code == EXIT_VALIDATION
    assert "unknown test" in err


def test_bad_alpha_is_validation_error(capsys):
    code, _, err = run(["-t", "indep", "-a", "1.5", "-p", ".8", "-e", ".5"], capsys)
    assert code == EXIT_VALIDATION


def test_an_a_priori_effect_below_1e5_is_refused_as_the_gui_does(capsys):
    """SPEC F-15: G*Power refuses |ES| < 1e-5 in an a-priori analysis; above
    it the search runs to G*Power's own 2**63 limit, so the answer exists."""
    code, _, err = run(
        ["-t", "regression-coef", "-s", "n", "-a", "0.001", "-p", "0.99",
         "-e", "1e-9", "--predictors", "1"],
        capsys,
    )
    assert code == EXIT_VALIDATION
    assert "1e-05" in err


def test_a_huge_but_finite_a_priori_answer_is_returned(capsys):
    code, out, _ = run(["-t", "one-sample", "-a", "0.05", "-p", "0.95",
                        "-e", "0.0001", "--json"], capsys)
    assert code == EXIT_OK
    doc = json.loads(out)
    assert doc["sample_size"]["total"] > 1_000_000_000
    assert any("SPEC F-14" in w for w in doc["warnings"])


def test_bad_param_syntax(capsys):
    code, _, err = run(
        ["-t", "generic", "-s", "power", "-a", ".05", "-e", "2", "--param", "df"],
        capsys,
    )
    assert code == EXIT_USAGE


# --------------------------------------------------------------------------
# list / info / curve / effect-size
# --------------------------------------------------------------------------
def test_list_json(capsys):
    code, out, _ = run(["list", "--json"], capsys)
    assert code == EXIT_OK
    doc = json.loads(out)
    assert doc["schema"] == "gpower-rea/tests/1"
    assert {t["key"] for t in doc["tests"]} == {
        "ttest-indep-means",
        "ttest-paired-means",
        "ttest-one-sample",
        "ttest-point-biserial",
        "ttest-regression-coef",
        "ttest-generic",
    }


def test_list_text(capsys):
    code, out, _ = run(["list"], capsys)
    assert code == EXIT_OK and "t tests" in out


def test_info(capsys):
    code, out, _ = run(["info", "point-biserial"], capsys)
    assert code == EXIT_OK
    assert "Point biserial" in out and "F-04" in out


def test_curve_csv(capsys):
    code, out, _ = run(
        ["curve", "-t", "one-sample", "-a", ".05", "-e", ".5",
         "--n-from", "20", "--n-to", "24", "--n-step", "2"],
        capsys,
    )
    assert code == EXIT_OK
    lines = out.strip().splitlines()
    assert len(lines) == 4  # header + 3 points


def test_effect_size_calculator(capsys):
    code, out, _ = run(
        ["effect-size", "-c", "d-two-independent-means",
         "--param", "mean1=10", "--param", "mean2=8",
         "--param", "sd1=4", "--param", "sd2=4", "--json"],
        capsys,
    )
    assert code == EXIT_OK
    doc = json.loads(out)
    assert doc["effect_size"]["value"] == pytest.approx(0.5)
    assert doc["for_test"] == "ttest-indep-means"


# --------------------------------------------------------------------------
# S-4: batch mode
# --------------------------------------------------------------------------
BATCH_CSV = """\
case,Statistical test,Type of power analysis,Tail(s),alpha err prob,Power (1-beta err prob),Effect size d,Allocation ratio N2/N1,expected_N
1,ttest-indep-means,n,2,0.05,0.95,0.5,1,210
2,ttest-indep-means,n,1,0.05,0.95,0.5,1,176
3,ttest-one-sample,n,2,0.05,0.95,0.5,,54
4,ttest-paired-means,n,2,0.05,0.95,0.5,,54
"""


def test_batch_csv_with_header_aliases(tmp_path, capsys):
    src = tmp_path / "vectors.csv"
    src.write_text(BATCH_CSV, encoding="utf-8")
    out_file = tmp_path / "out.csv"
    code, _, err = run(
        ["batch", "-i", str(src), "-o", str(out_file),
         "--expect", "expected_N", "--min-match", "1.0"],
        capsys,
    )
    assert code == EXIT_OK, err
    text = out_file.read_text(encoding="utf-8")
    assert "gp_N" in text and "gp_match" in text
    assert "exact_N_matches=4" in err
    assert text.count("yes") == 4


def test_batch_jsonl_roundtrip(tmp_path, capsys):
    src = tmp_path / "cases.jsonl"
    src.write_text(
        '{"test":"ttest-indep-means","solve":"n","alpha":0.05,"power":0.8,'
        '"effect_size":0.5,"tails":2}\n'
        '{"test":"ttest-one-sample","solve":"power","alpha":0.05,'
        '"effect_size":0.5,"n":40,"tails":2}\n',
        encoding="utf-8",
    )
    code, out, _ = run(["batch", "-i", str(src), "--format", "jsonl"], capsys)
    assert code == EXIT_OK
    rows = [json.loads(line) for line in out.strip().splitlines()]
    assert rows[0]["gp_N"] == 128
    assert rows[1]["gp_power"] == pytest.approx(0.8693, abs=5e-4)


def test_batch_defaults_from_flags(tmp_path, capsys):
    src = tmp_path / "min.csv"
    src.write_text("d\n0.5\n0.8\n", encoding="utf-8")
    code, out, _ = run(
        ["batch", "-i", str(src), "--test", "ttest-one-sample",
         "--solve", "n", "--alpha", "0.05", "--tails", "2",
         "--format", "jsonl", "--continue-on-error"],
        capsys,
    )
    assert code == EXIT_OK
    rows = [json.loads(line) for line in out.strip().splitlines()]
    # The `test`, `solve`, `alpha` and `tails` defaults were taken from the
    # flags, but there is no target power column, so solve=n must complain
    # rather than invent one.
    assert [r["gp_status"] for r in rows] == ["error", "error"]
    assert all("power" in r["gp_message"] for r in rows)


def test_batch_defaults_complete_a_runnable_row(tmp_path, capsys):
    src = tmp_path / "min2.csv"
    src.write_text("d,power\n0.5,0.8\n0.8,0.8\n", encoding="utf-8")
    code, out, _ = run(
        ["batch", "-i", str(src), "--test", "ttest-one-sample",
         "--solve", "n", "--alpha", "0.05", "--tails", "2",
         "--format", "jsonl"],
        capsys,
    )
    assert code == EXIT_OK
    rows = [json.loads(line) for line in out.strip().splitlines()]
    assert [r["gp_status"] for r in rows] == ["ok", "ok"]
    assert [r["gp_N"] for r in rows] == [34, 15]


def test_batch_min_match_gate_fails_loudly(tmp_path, capsys):
    src = tmp_path / "wrong.csv"
    src.write_text(
        "test,solve,tails,alpha,power,effect_size,expected_N\n"
        "ttest-one-sample,n,2,0.05,0.95,0.5,999\n",
        encoding="utf-8",
    )
    code, _, err = run(
        ["batch", "-i", str(src), "--expect", "expected_N", "--min-match", "0.9"],
        capsys,
    )
    assert code == EXIT_CONFORMANCE
    assert "FAIL" in err


def test_batch_continue_on_error(tmp_path, capsys):
    src = tmp_path / "mixed.csv"
    src.write_text(
        "test,solve,tails,alpha,power,effect_size\n"
        "ttest-one-sample,n,2,0.05,0.95,0.5\n"
        "nope,n,2,0.05,0.95,0.5\n",
        encoding="utf-8",
    )
    code, out, err = run(
        ["batch", "-i", str(src), "--format", "jsonl", "--continue-on-error"],
        capsys,
    )
    assert code == EXIT_OK
    rows = [json.loads(line) for line in out.strip().splitlines()]
    assert rows[0]["gp_status"] == "ok" and rows[1]["gp_status"] == "error"
    assert "1 row error" in err


def test_batch_custom_result_prefix(tmp_path, capsys):
    src = tmp_path / "p.csv"
    src.write_text(
        "test,solve,tails,alpha,power,effect_size\n"
        "ttest-one-sample,n,2,0.05,0.8,0.5\n",
        encoding="utf-8",
    )
    code, out, _ = run(
        ["batch", "-i", str(src), "--result-prefix", "", "--format", "jsonl"],
        capsys,
    )
    assert code == EXIT_OK
    row = json.loads(out.strip())
    assert row["N"] == 34


def test_batch_missing_file(capsys):
    code, _, err = run(["batch", "-i", "no-such-file.csv"], capsys)
    assert code == EXIT_USAGE


# --------------------------------------------------------------------------
# Robustness of batch input: the shapes a real vector file actually arrives in
# --------------------------------------------------------------------------
# Semicolon delimiter, Greek letters in the headers, G*Power's own analysis
# labels, decimal commas, an `NA`, and an expected-N column literally called
# "N" -- which must NOT be fed back in as the total sample size.
HOSTILE_CSV = (
    "case_id;Statistical test;Type of power analysis;Tail(s);"
    "α err prob;Power (1-β err prob);Effect size;"
    "Allocation ratio N2/N1;Number of predictors;N\n"
    "V001;ttest-indep-means;A priori;2;0,05;0,95;0,5;1;;210\n"
    "V002;indep;a priori;1;0,05;0,80;0,8;1;;42\n"
    "V003;ttest-one-sample;n;2;0,01;0,90;0,4;;;97\n"
    "V004;paired;n;2;0,05;0,80;0,35;;;67\n"
    "V005;point-biserial;n;2;0,05;0,80;0,3;;;82\n"
    "V006;regression-coef;n;1;0,05;0,95;0,15;;4;74\n"
    "V007;ttest-indep-means;n;2;0,05;0,90;0,42;2;;NA\n"
)


def test_batch_survives_a_hostile_vector_file(tmp_path, capsys):
    src = tmp_path / "hostile.csv"
    src.write_text(HOSTILE_CSV, encoding="utf-8")
    code, out, err = run(
        ["batch", "-i", str(src), "--expect", "N", "--format", "jsonl"],
        capsys,
    )
    assert code == EXIT_OK, err
    rows = [json.loads(line) for line in out.strip().splitlines()]
    assert len(rows) == 7
    assert all(r["gp_status"] == "ok" for r in rows), [
        r["gp_message"] for r in rows if r["gp_status"] != "ok"
    ]
    # Six rows carry an expectation; the NA row is skipped, not counted wrong.
    assert "compared=6 exact_N_matches=6" in err
    assert rows[0]["gp_N"] == 210 and rows[0]["gp_n1"] == 105
    assert rows[6]["gp_N"] == 270 and rows[6]["gp_n2"] == 180


def test_decimal_comma_is_accepted(tmp_path, capsys):
    src = tmp_path / "comma.csv"
    src.write_text(
        "test,solve,tails,alpha,power,effect_size\n"
        "ttest-one-sample,n,2,\"0,05\",\"0,95\",\"0,5\"\n",
        encoding="utf-8",
    )
    code, out, _ = run(["batch", "-i", str(src), "--format", "jsonl"], capsys)
    assert code == EXIT_OK
    assert json.loads(out.strip())["gp_N"] == 54


def test_thousands_separator_is_accepted(tmp_path, capsys):
    src = tmp_path / "thousands.csv"
    src.write_text(
        "test,solve,tails,alpha,effect_size,n\n"
        "ttest-one-sample,power,2,0.05,0.1,\"1,200\"\n",
        encoding="utf-8",
    )
    code, out, _ = run(["batch", "-i", str(src), "--format", "jsonl"], capsys)
    assert code == EXIT_OK
    row = json.loads(out.strip())
    assert row["gp_N"] == 1200


def test_expect_column_is_not_used_as_an_input(tmp_path, capsys):
    """A column named `N` holding the answer must not become the design."""
    src = tmp_path / "expect.csv"
    src.write_text(
        "test,solve,tails,alpha,power,effect_size,N\n"
        "ttest-one-sample,n,2,0.05,0.95,0.5,54\n",
        encoding="utf-8",
    )
    code, out, err = run(
        ["batch", "-i", str(src), "--expect", "N", "--format", "jsonl"], capsys
    )
    assert code == EXIT_OK
    row = json.loads(out.strip())
    assert row["gp_N"] == 54 and row["gp_match"] == "yes"
    assert "exact_N_matches=1" in err


@pytest.mark.parametrize(
    "label,expected",
    [
        ("A priori", "n"),
        ("a priori: compute required sample size", "n"),
        ("Post hoc", "power"),
        ("post hoc: compute achieved power", "power"),
        ("Criterion", "alpha"),
        ("Sensitivity", "effect-size"),
        ("Compromise", "compromise"),
    ],
)
def test_gpower_analysis_labels_are_accepted(label, expected, capsys):
    argv = ["-t", "indep", "-s", label, "--json", "-e", "0.5"]
    if expected == "n":
        argv += ["-a", "0.05", "-p", "0.8"]
    elif expected == "power":
        argv += ["-a", "0.05", "--n1", "40", "--n2", "40"]
    elif expected == "alpha":
        argv += ["-p", "0.8", "--n1", "40", "--n2", "40"]
    elif expected == "effect-size":
        argv = ["-t", "indep", "-s", label, "--json", "-a", "0.05", "-p", "0.8",
                "--n1", "40", "--n2", "40"]
    else:
        argv += ["--n1", "40", "--n2", "40", "--q", "2"]
    code, out, err = run(argv, capsys)
    assert code == EXIT_OK, err
    assert json.loads(out)["solve_for"] == expected


def test_unknown_analysis_label_names_the_alternatives(capsys):
    code, _, err = run(
        ["-t", "indep", "-s", "bayesian", "-a", ".05", "-p", ".8", "-e", ".5"],
        capsys,
    )
    assert code == EXIT_VALIDATION
    assert "a priori" in err and "compromise" in err


def test_missing_parameters_are_named(capsys):
    code, _, err = run(["-t", "indep", "-s", "n", "-a", "0.05"], capsys)
    assert code == EXIT_VALIDATION
    assert "missing: power, effect-size" in err


# --------------------------------------------------------------------------
# selftest and the real console script
# --------------------------------------------------------------------------
def test_selftest_passes(capsys):
    code, out, _ = run(["selftest"], capsys)
    assert code == EXIT_OK
    assert "0 finding(s)" in out
    assert "rate 1.0000" in out


def test_console_script_is_installed():
    proc = subprocess.run(
        [sys.executable, "-m", "gpower_rea", "version"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "gpower" in proc.stdout


# --------------------------------------------------------------------------
# Hidden-vector robustness: files written in G*Power's own vocabulary
# --------------------------------------------------------------------------
GUI_TITLES = {
    "Means: Difference between two independent means (two groups)": "ttest-indep-means",
    "Means: Difference between two dependent means (matched pairs)": "ttest-paired-means",
    "Means: Difference from constant (one sample case)": "ttest-one-sample",
    "Correlation: Point biserial model": "ttest-point-biserial",
    "Linear multiple regression: Fixed model, single regression coefficient": "ttest-regression-coef",
    "Generic t test": "ttest-generic",
    "t tests - Means: Difference between two independent means (two groups)": "ttest-indep-means",
}


@pytest.mark.parametrize("title,key", list(GUI_TITLES.items()))
def test_gui_menu_titles_resolve(title, key):
    from gpower_rea.procedures import resolve

    assert resolve(title).key == key


@pytest.mark.parametrize("word,expected", [
    ("One", 1), ("Two", 2), ("two-tailed", 2), ("one-sided", 1), ("2", 2), ("1.0", 1),
])
def test_tails_accepts_the_gui_wording(word, expected):
    from gpower_rea.cli import parse_tails

    assert parse_tails(word) == expected


def test_tails_rejects_three():
    from gpower_rea.cli import parse_tails
    from gpower_rea.procedures import ValidationError

    with pytest.raises(ValidationError):
        parse_tails("3")


def test_batch_in_gpower_vocabulary(tmp_path, capsys):
    f = tmp_path / "v.csv"
    f.write_text(
        "Statistical test;Type of power analysis;Tail(s);α err prob;"
        "Power (1-β err prob);Effect size d;Allocation ratio N2/N1;N\n"
        "Means: Difference between two independent means (two groups);"
        "A priori;Two;0,05;0,95;0,5;2;236\n"
        "Means: Difference between two independent means (two groups);"
        "A priori;Two;0,05;0,95;0,5;1,5;220\n",
        encoding="utf-8",
    )
    code, _, err = run(["batch", "-i", str(f), "--expect", "N",
                        "--min-match", "1.0", "-o", str(tmp_path / "o.csv")], capsys)
    assert code == EXIT_OK, err
    assert "exact_N_matches=2" in err
