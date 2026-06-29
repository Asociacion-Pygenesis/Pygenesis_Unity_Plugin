from models import SelectionData


def is_empty_selection(selection: SelectionData | None) -> bool:
    if selection is None:
        return True

    if (
        selection.name == ""
        and selection.type == ""
        and not selection.has_collider
        and not selection.has_renderer
        and not selection.has_animator
        and not selection.has_rigidbody
    ):
        if selection.transform is None:
            return True

        if (
            len(selection.transform.position) == 0
            and len(selection.transform.rotation) == 0
            and len(selection.transform.scale) == 0
        ):
            return True

    return False