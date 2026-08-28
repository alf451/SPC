from datetime import datetime

from sqlalchemy import ForeignKey, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PartFolder(Base):
    __tablename__ = "part_folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("part_folders.id"))
    name: Mapped[str]


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("part_folders.id"))
    name: Mapped[str]
    description: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class PartPropertyVersion(Base):
    """Proprietà versionate del Part (nominale/limiti) — equivalente PartProperties + PropID di MeasurLink.

    Ogni modifica crea una nuova riga con valid_from=now(); la versione precedente
    riceve valid_to=now(). I dati storici referenziano sempre la versione attiva
    al momento della raccolta, così un cambio di limiti non altera lo storico.
    """

    __tablename__ = "part_property_versions"
    __table_args__ = (UniqueConstraint("part_id", "version_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="CASCADE"))
    version_no: Mapped[int]
    sample_size: Mapped[int | None]
    default_control_chart: Mapped[str | None]
    limit_calc_type: Mapped[str | None]
    lower_control_limit: Mapped[float | None]
    center_line: Mapped[float | None]
    upper_control_limit: Mapped[float | None]
    decimal_length: Mapped[int | None]
    rounded: Mapped[bool] = mapped_column(default=True)
    valid_from: Mapped[datetime] = mapped_column(server_default="now()")
    valid_to: Mapped[datetime | None]
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class RoutineFolder(Base):
    __tablename__ = "routine_folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("routine_folders.id"))
    name: Mapped[str]


class Routine(Base):
    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(primary_key=True)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("routine_folders.id"))
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="CASCADE"))
    feature_type: Mapped[str]  # "variable" | "attribute"
    name: Mapped[str]
    description: Mapped[str | None]
    order_no: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class FeaturePropertyVersion(Base):
    """Nominale/tolleranze/limiti di controllo versionati — equivalente FeatureProperties + PropID."""

    __tablename__ = "feature_property_versions"
    __table_args__ = (UniqueConstraint("feature_id", "version_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    feature_id: Mapped[int] = mapped_column(ForeignKey("features.id", ondelete="CASCADE"))
    version_no: Mapped[int]
    target: Mapped[float | None]
    lower_tolerance_limit: Mapped[float | None]
    upper_tolerance_limit: Mapped[float | None]
    lower_warning_limit: Mapped[float | None]
    upper_warning_limit: Mapped[float | None]
    subgroup_size: Mapped[int] = mapped_column(default=1)
    control_method: Mapped[str | None]
    lower_control_limit_x: Mapped[float | None]
    center_line_x: Mapped[float | None]
    upper_control_limit_x: Mapped[float | None]
    lower_control_limit_r: Mapped[float | None]
    center_line_r: Mapped[float | None]
    upper_control_limit_r: Mapped[float | None]
    sigma_estimate: Mapped[float | None]
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    decimal_length: Mapped[int] = mapped_column(default=3)
    rounded: Mapped[bool] = mapped_column(default=True)
    tolerance_standard: Mapped[str | None]
    tolerance_grade: Mapped[str | None]
    valid_from: Mapped[datetime] = mapped_column(server_default="now()")
    valid_to: Mapped[datetime | None]
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class RoutineFeature(Base):
    __tablename__ = "routine_features"

    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id", ondelete="CASCADE"), primary_key=True)
    feature_id: Mapped[int] = mapped_column(ForeignKey("features.id", ondelete="CASCADE"), primary_key=True)
    order_no: Mapped[int] = mapped_column(default=0)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id"))
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    name: Mapped[str]
    status: Mapped[str] = mapped_column(default="active")  # active | completed | aborted
    started_at: Mapped[datetime] = mapped_column(server_default="now()")
    ended_at: Mapped[datetime | None]
    started_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Measurement(Base):
    """Misura variabile singola — equivalente FeatureRunData. Tabella partizionata per captured_at."""

    __tablename__ = "measurements"
    __table_args__ = (PrimaryKeyConstraint("id", "captured_at"),)

    id: Mapped[int] = mapped_column(autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    feature_id: Mapped[int] = mapped_column(ForeignKey("features.id"))
    obs_no: Mapped[int]
    value: Mapped[float | None]
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    flags: Mapped[int] = mapped_column(default=0)
    captured_at: Mapped[datetime]
    received_at: Mapped[datetime] = mapped_column(server_default="now()")
    source: Mapped[str] = mapped_column(default="daq")  # daq | manual | import


class AttributeObservation(Base):
    """Osservazione pass/fail singola — equivalente AttFeatureRunData. Tabella partizionata."""

    __tablename__ = "attribute_observations"
    __table_args__ = (PrimaryKeyConstraint("id", "captured_at"),)

    id: Mapped[int] = mapped_column(autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    feature_id: Mapped[int] = mapped_column(ForeignKey("features.id"))
    obs_no: Mapped[int]
    defect_count: Mapped[int] = mapped_column(default=0)
    captured_at: Mapped[datetime]
    received_at: Mapped[datetime] = mapped_column(server_default="now()")


class AttributeSubgroup(Base):
    """Riepilogo per sottogruppo (p/np/c/u chart) — equivalente AttSubgroupData."""

    __tablename__ = "attribute_subgroups"
    __table_args__ = (UniqueConstraint("run_id", "subgroup_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"))
    subgroup_no: Mapped[int]
    sample_size: Mapped[int]
    inspected_count: Mapped[int]
    defective_count: Mapped[int]
    captured_at: Mapped[datetime] = mapped_column(server_default="now()")


class ControlLimits(Base):
    __tablename__ = "control_limits"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    feature_id: Mapped[int] = mapped_column(ForeignKey("features.id"))
    computed_at: Mapped[datetime] = mapped_column(server_default="now()")
    lcl_x: Mapped[float | None]
    cl_x: Mapped[float | None]
    ucl_x: Mapped[float | None]
    lcl_r: Mapped[float | None]
    cl_r: Mapped[float | None]
    ucl_r: Mapped[float | None]
    locked: Mapped[bool] = mapped_column(default=False)


class CapabilityResult(Base):
    __tablename__ = "capability_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    feature_id: Mapped[int] = mapped_column(ForeignKey("features.id"))
    computed_at: Mapped[datetime] = mapped_column(server_default="now()")
    sample_size: Mapped[int | None]
    cp: Mapped[float | None]
    cpk: Mapped[float | None]
    pp: Mapped[float | None]
    ppk: Mapped[float | None]


class CapabilityTestFailure(Base):
    """Log violazioni soglie capability — equivalente CapabilityTestFail (tabella a volume più alto in MeasurLink)."""

    __tablename__ = "capability_test_failures"
    __table_args__ = (PrimaryKeyConstraint("id", "occurred_at"),)

    id: Mapped[int] = mapped_column(autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    feature_id: Mapped[int] = mapped_column(ForeignKey("features.id"))
    index_name: Mapped[str]
    value: Mapped[float | None]
    threshold: Mapped[float | None]
    occurred_at: Mapped[datetime] = mapped_column(server_default="now()")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    feature_id: Mapped[int | None] = mapped_column(ForeignKey("features.id"))
    obs_id: Mapped[int | None]
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    feature_id: Mapped[int | None] = mapped_column(ForeignKey("features.id"))
    assignable_cause: Mapped[str | None]
    description: Mapped[str]
    status: Mapped[str] = mapped_column(default="open")
    created_at: Mapped[datetime] = mapped_column(server_default="now()")


class TraceabilityField(Base):
    __tablename__ = "traceability_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    field_type: Mapped[str] = mapped_column(default="text")
    pick_list: Mapped[dict | None] = mapped_column(JSONB)


class RunTraceabilityValue(Base):
    __tablename__ = "run_traceability_values"

    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("traceability_fields.id"), primary_key=True)
    value: Mapped[str | None]
