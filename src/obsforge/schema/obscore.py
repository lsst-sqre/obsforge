"""SQLAlchemy schema for the ObsCore table."""

from sqlalchemy import DDL, BigInteger, Float, Integer, event
from sqlalchemy.orm import Mapped, mapped_column

from .base import SchemaBase

__all__ = ["ObsCore"]

_IVOA_SCHEMA = "ivoa"


event.listen(
    SchemaBase.metadata,
    "before_create",
    DDL(f"CREATE SCHEMA IF NOT EXISTS {_IVOA_SCHEMA}"),
)


def _info(unit: str, description: str, ucd: str) -> dict[str, str]:
    return {"unit": unit, "description": description, "ucd": ucd}


class ObsCore(SchemaBase):
    """ObsCore observation metadata enriched by ObsForge."""

    __tablename__ = "ObsCore"
    __table_args__ = ({"schema": _IVOA_SCHEMA},)

    dataproduct_type: Mapped[str] = mapped_column(
        nullable=False,
        info=_info(
            "",
            "Data product (file content) primary type",
            "meta.code.class",
        ),
    )
    dataproduct_subtype: Mapped[str] = mapped_column(
        nullable=False,
        info=_info("", "Data product specific type", "meta.code.class"),
    )
    calib_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        info=_info(
            "",
            "Calibration level of the observation: in {0, 1, 2, 3, 4}",
            "meta.code;obs.calib",
        ),
    )
    target_name: Mapped[str | None] = mapped_column(
        nullable=True, info=_info("", "Object of interest", "meta.id;src")
    )
    obs_id: Mapped[str] = mapped_column(
        primary_key=True,
        info=_info("", "Internal ID given by the ObsTAP service", "meta.id"),
    )
    obs_collection: Mapped[str] = mapped_column(
        nullable=False,
        info=_info("", "Name of the data collection", "meta.id"),
    )
    obs_publisher_did: Mapped[str] = mapped_column(
        nullable=False,
        info=_info(
            "",
            "ID for the Dataset given by the publisher",
            "meta.ref.ivoid",
        ),
    )
    access_url: Mapped[str] = mapped_column(
        nullable=False,
        info=_info("", "URL used to access dataset", "meta.ref.url"),
    )
    access_format: Mapped[str] = mapped_column(
        nullable=False,
        info=_info("", "Content format of the dataset", "meta.code.mime"),
    )
    access_estsize: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        info=_info(
            "kbyte", "Estimated size of dataset in kilobytes", "meta.id"
        ),
    )
    s_ra: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        info=_info(
            "deg",
            "Central Spatial Position in ICRS; Right ascension",
            "pos.eq.ra",
        ),
    )
    s_dec: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        info=_info(
            "deg",
            "Central Spatial Position in ICRS; Declination",
            "pos.eq.dec",
        ),
    )
    s_fov: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        info=_info(
            "deg",
            "Estimated size of the covered region as the diameter of a "
            "containing circle",
            "phys.angSize;instr.fov",
        ),
    )
    s_region: Mapped[str] = mapped_column(
        nullable=False,
        info=_info(
            "",
            "Sky region covered by the data product (expressed in ICRS frame)",
            "pos.outline;obs.field",
        ),
    )
    s_resolution: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        info=_info(
            "arcsec",
            "Spatial resolution of data as FWHM of PSF",
            "pos.angResolution",
        ),
    )
    s_xel1: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        info=_info(
            "",
            "Number of elements along the first coordinate of the spatial "
            "axis",
            "meta.number",
        ),
    )
    s_xel2: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        info=_info(
            "",
            "Number of elements along the second coordinate of the spatial "
            "axis",
            "meta.number",
        ),
    )
    t_xel: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        info=_info(
            "", "Number of elements along the time axis", "meta.number"
        ),
    )
    t_min: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        info=_info("d", "Start time in MJD", "time.start;obs.exposure"),
    )
    t_max: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        info=_info("d", "Stop time in MJD", "time.end;obs.exposure"),
    )
    t_exptime: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        info=_info("s", "Total exposure time", "time.duration;obs.exposure"),
    )
    t_resolution: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        info=_info("s", "Temporal resolution FWHM", "time.resolution"),
    )
    em_xel: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        info=_info(
            "", "Number of elements along the spectral axis", "meta.number"
        ),
    )
    em_min: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        info=_info("m", "start in spectral coordinates", "em.wl;stat.min"),
    )
    em_max: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        info=_info("m", "stop in spectral coordinates", "em.wl;stat.max"),
    )
    em_res_power: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        info=_info(
            "",
            "Value of the resolving power along the spectral axis (R)",
            "spect.resolution",
        ),
    )
    o_ucd: Mapped[str] = mapped_column(
        nullable=False,
        info=_info("", "Nature of the observable axis", "meta.ucd"),
    )
    pol_xel: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        info=_info(
            "",
            "Number of elements along the polarization axis",
            "meta.number",
        ),
    )
    instrument_name: Mapped[str] = mapped_column(
        nullable=False,
        info=_info(
            "",
            "The name of the instrument used for the observation",
            "meta.id;instr",
        ),
    )
    facility_name: Mapped[str] = mapped_column(
        nullable=False,
        info=_info(
            "",
            "The name of the facility, telescope, or space craft used for "
            "the observation",
            "meta.id;instr.tel",
        ),
    )
    obs_title: Mapped[str] = mapped_column(
        nullable=False,
        info=_info(
            "",
            "Brief description of dataset in free format",
            "meta.title;obs",
        ),
    )
    em_filter_name: Mapped[str] = mapped_column(
        nullable=False,
        info=_info(
            "",
            "Filter name associated with the observation spectral coverage",
            "meta.id;instr.filter",
        ),
    )
    lsst_visit: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        info=_info(
            "",
            "Identifier for a specific LSSTCam pointing",
            "meta.id;obs",
        ),
    )
    lsst_detector: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        info=_info(
            "",
            "Identifier for CCD within the LSSTCam focal plane",
            "meta.id;instr.det",
        ),
    )
    lsst_filter: Mapped[str] = mapped_column(
        nullable=False,
        info=_info(
            "",
            "Physical filter designation from the LSSTCam filter set",
            "meta.id;instr.filter",
        ),
    )
    lsst_band: Mapped[str] = mapped_column(
        nullable=False,
        info=_info(
            "",
            "Abstract filter band designation",
            "meta.id;instr.filter",
        ),
    )
    lsst_patch: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        info=_info(
            "",
            "Lower level of LSST coadd skymap hierarchy",
            "meta.id.part",
        ),
    )
    lsst_tract: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        info=_info(
            "",
            "Upper level of LSST coadd skymap hierarchy",
            "meta.id",
        ),
    )
