"""Tiny dependency-free PDF writer for prototype incident packets."""
from __future__ import annotations


def _safe(value: object) -> str:
    return str(value).encode("ascii", "replace").decode("ascii").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def incident_pdf(report: dict) -> bytes:
    incident = report["incident"]
    lines = [
        "CAT COMMANDGUARD - SYNTHETIC INCIDENT REPORT",
        f"Incident: {incident.get('incident_id')}",
        f"Machine: {incident.get('machine_id')}   Operator: {incident.get('operator_id')}",
        f"Task: {incident.get('task_type')}   Severity: {incident.get('severity')}",
        f"Status: {report.get('outcome')}",
        "",
        "EVIDENCE",
    ]
    lines.extend(f"- {item.get('signal')}: {item.get('observation')} Expected: {item.get('expected')}" for item in incident.get("evidence", []))
    lines.extend(["", "OPERATOR ACTIONS"])
    lines.extend(f"- {item.get('timestamp')}: {item.get('message')}" for item in report.get("operator_actions", []))
    lines.extend(["", "FOLLOW-UP", report.get("recommended_follow_up", ""), "", "Synthetic data only. Not a machine repair instruction."])
    lines = [line[:115] for line in lines]
    content_lines = ["BT", "/F1 10 Tf", "50 760 Td"]
    for line in lines:
        content_lines.append(f"({_safe(line)}) Tj")
        content_lines.append("0 -15 Td")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("ascii", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(output)
