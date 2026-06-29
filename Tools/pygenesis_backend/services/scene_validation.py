from models import SceneSnapshotData


def is_empty_scene_snapshot(snapshot: SceneSnapshotData | None) -> bool:
    if snapshot is None:
        return True
    if snapshot.roots:
        return False
    if snapshot.flat_sample:
        return False
    return snapshot.root_count <= 0 and snapshot.total_estimated <= 0
