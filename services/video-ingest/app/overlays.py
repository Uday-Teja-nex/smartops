"""Burn measured boxes into the exact frame that produced them."""
import cv2


def annotate(image, detections):
    output = image.copy()
    height, width = output.shape[:2]
    for detection in detections:
        box = detection['bbox']
        x1, y1 = round(box['x'] * width), round(box['y'] * height)
        x2 = min(width - 1, round((box['x'] + box['w']) * width))
        y2 = min(height - 1, round((box['y'] + box['h']) * height))
        cv2.rectangle(output, (x1, y1), (x2, y2), (80, 220, 80), 2)
        label = f"{detection['label']} {detection['confidence']:.0%}"
        cv2.putText(output, label, (x1, max(12, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX,
                    .4, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(output, label, (x1, max(12, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX,
                    .4, (255, 255, 255), 1, cv2.LINE_AA)
    return output
