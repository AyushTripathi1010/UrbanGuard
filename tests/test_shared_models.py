from shared import Alert, Frame, RLFeedback, SeverityTier


def test_frame_roundtrips():
    frame = Frame(
        frame_id="f1",
        camera_id="cam-001",
        zone_id="z3",
        width=1280,
        height=720,
        jpeg_bytes_b64="",
    )
    dumped = frame.model_dump_json()
    assert Frame.model_validate_json(dumped) == frame


def test_alert_construction():
    alert = Alert(
        alert_id="a1",
        frame_id="f1",
        camera_id="cam-001",
        zone_id="z3",
        clip_label="accident",
        clip_score=0.82,
        resnet_severity=0.61,
    )
    assert 0 <= alert.clip_score <= 1
    assert 0 <= alert.resnet_severity <= 1


def test_rl_feedback_flags_consistent():
    fb = RLFeedback(
        alert_id="a1",
        zone_id="z3",
        detected_early=True,
        was_false_alarm=False,
        was_missed=False,
        compute_frames_used=12,
    )
    assert not (fb.was_false_alarm and fb.detected_early)


def test_severity_tier_values():
    assert SeverityTier("high") == SeverityTier.high
    assert list(SeverityTier) == [
        SeverityTier.none,
        SeverityTier.low,
        SeverityTier.medium,
        SeverityTier.high,
        SeverityTier.critical,
    ]
