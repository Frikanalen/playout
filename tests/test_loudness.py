import math

import pytest

from playout_lib.loudness import (
    MAX_PLAUSIBLE_TRUEPEAK_DBTP,
    SILENCE_FLOOR_LUFS,
    db_to_multiplier,
    playback_gain_db,
)

# Defaults the production config ships with, pinned here so the cases below
# stay readable and do not drift with the environment the tests run in.
TARGET = -23.0
MAX_BOOST = 12.0
CEILING = -1.0


def gain(integrated_lufs, truepeak_dbtp=None):
    return playback_gain_db(
        integrated_lufs,
        truepeak_dbtp,
        target_lufs=TARGET,
        max_boost_db=MAX_BOOST,
        truepeak_ceiling_dbtp=CEILING,
    )


class TestPlaybackGain:
    def test_lifts_a_quiet_file_to_target(self):
        assert gain(-27.0, truepeak_dbtp=-12.0) == pytest.approx(4.0)

    def test_attenuates_a_loud_file_to_target(self):
        assert gain(-16.0, truepeak_dbtp=-0.2) == pytest.approx(-7.0)

    def test_leaves_an_on_target_file_alone(self):
        assert gain(TARGET, truepeak_dbtp=-2.0) == pytest.approx(0.0)

    def test_a_measured_file_never_ends_up_over_the_ceiling(self):
        # The property the whole thing exists to guarantee: there is no
        # limiter downstream, so peak + gain must land under the ceiling.
        for lufs in (-40.0, -31.0, -23.0, -16.0, -5.0):
            for peak in (-30.0, -12.0, -1.0, -0.1, 0.0, 3.0, 11.0):
                applied = gain(lufs, truepeak_dbtp=peak)
                assert peak + applied <= CEILING + 1e-9, f"{lufs} LUFS / {peak} dBTP"


class TestMissingMeasurements:
    @pytest.mark.parametrize("value", [None, "unmeasured", float("nan"), float("-inf")])
    def test_unusable_integrated_loudness_means_no_gain(self, value):
        assert gain(value) is None

    def test_silence_is_not_amplified(self):
        assert gain(SILENCE_FLOOR_LUFS) is None
        assert gain(SILENCE_FLOOR_LUFS - 1.0) is None

    def test_unusable_truepeak_is_ignored_rather_than_fatal(self):
        assert gain(-27.0, truepeak_dbtp=float("nan")) == pytest.approx(0.0)

    def test_an_implausible_loudness_is_not_acted_on(self):
        # Real programme material does not average above 0 LUFS; the library
        # holds a few records that do, and they are measurement faults.
        assert gain(5.0, truepeak_dbtp=-2.0) is None


class TestUnmeasuredPeak:
    """Without a peak we cannot promise anything, so we must not add level."""

    def test_a_quiet_file_is_not_boosted_blind(self):
        assert gain(-31.0, truepeak_dbtp=None) == pytest.approx(0.0)

    def test_a_loud_file_is_still_turned_down(self):
        # Attenuation cannot clip, so it stays available without a peak.
        assert gain(-14.0, truepeak_dbtp=None) == pytest.approx(-9.0)

    def test_an_implausible_peak_is_treated_as_no_peak(self):
        # Obeying a +80 dBTP reading literally would mute the programme.
        assert gain(-31.0, truepeak_dbtp=80.15) == pytest.approx(0.0)
        assert gain(-14.0, truepeak_dbtp=80.15) == pytest.approx(-9.0)

    def test_the_plausibility_edge_is_still_honoured(self):
        assert gain(-31.0, truepeak_dbtp=MAX_PLAUSIBLE_TRUEPEAK_DBTP) == pytest.approx(-13.0)


class TestBoostLimits:
    def test_boost_is_capped(self):
        # -45 LUFS would want +22 dB; a measurement that far off is more
        # likely wrong than genuinely that quiet.
        assert gain(-45.0, truepeak_dbtp=-40.0) == pytest.approx(MAX_BOOST)

    def test_boost_is_held_back_to_leave_truepeak_headroom(self):
        # Wants +8 dB but only 3 dB of headroom is left below the ceiling.
        assert gain(-31.0, truepeak_dbtp=-4.0) == pytest.approx(3.0)

    def test_a_file_already_over_the_ceiling_is_pulled_down_to_it(self):
        # Half the library peaks above -1 dBTP, and with no limiter downstream
        # the only way under the ceiling is to turn the file down.
        assert gain(-31.0, truepeak_dbtp=0.5) == pytest.approx(-1.5)
        assert gain(-23.0, truepeak_dbtp=0.5) == pytest.approx(-1.5)

    def test_loudness_wins_when_it_asks_for_more_cut_than_the_ceiling(self):
        # -10 LUFS wants -13 dB; the ceiling would only ask for -1.5 dB.
        assert gain(-10.0, truepeak_dbtp=0.5) == pytest.approx(-13.0)


class TestMultiplier:
    def test_unity_gain_is_unity_volume(self):
        assert db_to_multiplier(0.0) == pytest.approx(1.0)

    def test_six_db_roughly_doubles_amplitude(self):
        assert db_to_multiplier(6.02) == pytest.approx(2.0, rel=1e-3)

    def test_attenuation_is_below_unity(self):
        assert db_to_multiplier(-20.0) == pytest.approx(0.1)

    def test_result_is_always_a_finite_positive_number(self):
        for db in (-40.0, -1.0, 0.0, 1.0, 12.0):
            assert math.isfinite(db_to_multiplier(db))
            assert db_to_multiplier(db) > 0
