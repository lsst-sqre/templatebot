"""Test for the variablesmodal module."""

from __future__ import annotations

from pathlib import Path

import pytest
from templatekit.repo import FileTemplate, ProjectTemplate

from templatebot.storage.slack.variablesmodal import (
    TemplateVariablesModal,
    TemplateVariablesModalMetadata,
)


@pytest.fixture
def templates_dir() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "templates"


def test_template_variables_modal_for_copyright(templates_dir: Path) -> None:
    """Test the TemplateVariablesModal with the copyright template."""
    template = FileTemplate(
        str(templates_dir / "file_templates" / "copyright")
    )
    git_ref = "main"
    repo_url = "https://github.com/lsst/templates"
    trigger_message_ts = "1234567890.123456"
    trigger_channel_id = "C12345678"

    modal = TemplateVariablesModal.create(
        template=template,
        git_ref=git_ref,
        repo_url=repo_url,
        trigger_message_ts=trigger_message_ts,
        trigger_channel_id=trigger_channel_id,
    )

    # Check that the metadata can be loaded from the modal
    assert modal.private_metadata is not None
    metadata = TemplateVariablesModalMetadata.model_validate_json(
        modal.private_metadata
    )
    assert metadata.type == "file"

    # Check that the modal has the expected title
    assert modal.title.text == "Create a COPYRIGHT"

    # Check that the modal has the expected blocks
    assert len(modal.blocks) == 1
    assert modal.blocks[0].type == "input"
    assert modal.blocks[0].element.type == "static_select"
    assert modal.blocks[0].element.options is not None
    assert (
        modal.blocks[0].element.options[0].text.text
        == "Association of Universities for Research in Astronomy, Inc. (AURA)"
    )


def test_template_variables_modal_for_fastapi(templates_dir: Path) -> None:
    """Test the TemplateVariablesModal with the FastAPI template."""
    template = ProjectTemplate(
        str(templates_dir / "project_templates" / "safir_fastapi_app")
    )
    git_ref = "main"
    repo_url = "https://github.com/lsst/templates"
    trigger_message_ts = "1234567890.123456"
    trigger_channel_id = "C12345678"

    modal = TemplateVariablesModal.create(
        template=template,
        git_ref=git_ref,
        repo_url=repo_url,
        trigger_message_ts=trigger_message_ts,
        trigger_channel_id=trigger_channel_id,
    )

    # Check that the metadata can be loaded from the modal
    assert modal.private_metadata is not None
    metadata = TemplateVariablesModalMetadata.model_validate_json(
        modal.private_metadata
    )
    assert metadata.type == "project"


def test_template_variables_modal_for_technote(templates_dir: Path) -> None:
    """Test the TemplateVariablesModal with the technote template."""
    template = ProjectTemplate(
        str(templates_dir / "project_templates" / "technote_rst")
    )
    git_ref = "main"
    repo_url = "https://github.com/lsst/templates"
    trigger_message_ts = "1234567890.123456"
    trigger_channel_id = "C12345678"

    modal = TemplateVariablesModal.create(
        template=template,
        git_ref=git_ref,
        repo_url=repo_url,
        trigger_message_ts=trigger_message_ts,
        trigger_channel_id=trigger_channel_id,
    )

    # Check that the metadata can be loaded from the modal
    assert modal.private_metadata is not None
    metadata = TemplateVariablesModalMetadata.model_validate_json(
        modal.private_metadata
    )
    assert metadata.type == "project"


def test_template_variables_modal_for_stack_package(
    templates_dir: Path,
) -> None:
    """Test the TemplateVariablesModal with the stack_package template."""
    template = ProjectTemplate(
        str(templates_dir / "project_templates" / "stack_package")
    )
    git_ref = "main"
    repo_url = "https://github.com/lsst/templates"
    trigger_message_ts = "1234567890.123456"
    trigger_channel_id = "C12345678"

    modal = TemplateVariablesModal.create(
        template=template,
        git_ref=git_ref,
        repo_url=repo_url,
        trigger_message_ts=trigger_message_ts,
        trigger_channel_id=trigger_channel_id,
    )

    # Check that the metadata can be loaded from the modal
    assert modal.private_metadata is not None
    metadata = TemplateVariablesModalMetadata.model_validate_json(
        modal.private_metadata
    )
    assert metadata.type == "project"
