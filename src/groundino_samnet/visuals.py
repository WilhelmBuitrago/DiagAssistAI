import supervision as sv
from groundingdino.util.inference import annotate
import matplotlib.pyplot as plt
import numpy as np
from .utils import convert_image_to_numpy

def plot_grid(images,idss,boxes,logits,phrases,**args):
  imag_max = args.get("image_max",10) #cambiado, truncado de 20 a 10
  if len(images) > imag_max:
    print(f"Warning: The amount displayed will be truncated to 10. You can change this value using the image_max argument, but there is a risk of not displaying the images correctly.")
    images = images[:20]
    idss = idss[:20]
    boxes = boxes[:20]
    logits = logits[:20]
    phrases = phrases[:20]
    images = [convert_image_to_numpy(image) for image in images]
  annotated_frames = []
  for i in range(len(boxes)):
    annotated_frame = annotate(image_source=images[i], boxes=boxes[i], logits=logits[i], phrases=phrases[i])
    annotated_frames.append(annotated_frame)
  sv.plot_images_grid(
    images=annotated_frames,
    grid_size=(8, int(len(annotated_frames) / 8)+1),
    size=(15, 15),
    titles=idss
  )

def plot_image(image,boxes,logits,phrases):
  convert_image_to_numpy(image)
  annotated_frame = annotate(image_source=image, boxes=boxes, logits=logits, phrases=phrases)
  sv.plot_image(annotated_frame, (16, 16))


#Code from SAM2
np.random.seed(3)

def show_mask(mask, ax, random_color=False, borders = True):
    if random_color:
        color = np.concatenate([np.random.random(3), np.array([0.6])], axis=0)
    else:
        color = np.array([30/255, 144/255, 255/255, 0.6])
    h, w = mask.shape[-2:]
    mask = mask.astype(np.uint8)
    mask_image =  mask.reshape(h, w, 1) * color.reshape(1, 1, -1)
    if borders:
        import cv2
        contours, _ = cv2.findContours(mask,cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE) 
        # Try to smooth contours
        contours = [cv2.approxPolyDP(contour, epsilon=0.01, closed=True) for contour in contours]
        mask_image = cv2.drawContours(mask_image, contours, -1, (1, 1, 1, 0.5), thickness=2) 
    ax.imshow(mask_image)

def show_points(coords, labels, ax, marker_size=375):
    pos_points = coords[labels==1]
    neg_points = coords[labels==0]
    ax.scatter(pos_points[:, 0], pos_points[:, 1], color='green', marker='*', s=marker_size, edgecolor='white', linewidth=1.25)
    ax.scatter(neg_points[:, 0], neg_points[:, 1], color='red', marker='*', s=marker_size, edgecolor='white', linewidth=1.25)   

def show_box(box, ax):
    x0, y0 = box[0], box[1]
    w, h = box[2] - box[0], box[3] - box[1]
    ax.add_patch(plt.Rectangle((x0, y0), w, h, edgecolor='green', facecolor=(0, 0, 0, 0), lw=2))    

def show_masks(image, masks, scores, point_coords=None, box_coords=None, input_labels=None, borders=True):
    for i, (mask, score) in enumerate(zip(masks, scores)):
        plt.figure(figsize=(10, 10))
        plt.imshow(image)
        show_mask(mask, plt.gca(), borders=borders)
        if point_coords is not None:
            assert input_labels is not None
            show_points(point_coords, input_labels, plt.gca())
        if box_coords is not None:
            # boxes
            show_box(box_coords, plt.gca())
        if len(scores) > 1:
            plt.title(f"Mask {i+1}, Score: {score:.3f}", fontsize=18)
        plt.axis('off')
        plt.show()