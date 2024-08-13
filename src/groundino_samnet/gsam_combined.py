import sys
import os
import torch
import numpy as np
from PIL import Image
from huggingface_hub import hf_hub_download
from typing import List,Union, Tuple,Optional

from segment_anything.build_sam import sam_model_registry
from segment_anything.predictor import SamPredictor
from segment_anything.config import (SAM1_MODELS,
                                     SAM_NAMES_MODELS)
from groundingdino.util.inference import (predict,
                             load_model)
from groundingdino.util import box_ops

class GSamNetwork():
    def __init__(self,SAM:str,SAM_MODEL:Optional[str]):

        if not isinstance(SAM, str):
            raise TypeError(f"The SAM model should be a single value, not a list or collection. Please provide one of the following valid model names: {SAM_NAMES_MODELS}.")
        if SAM not in SAM_NAMES_MODELS:
            raise ValueError(f"The specified SAM model '{SAM}' does not exist. Please select a valid model from the following options: {SAM_NAMES_MODELS}.")
        
        self.__file_path = os.path.dirname(os.path.abspath(__file__))
        self.weights_path = os.path.join(self.__file_path, "weights")
        self.default_sam1 = "vit_h"
        self.default_sam2 = "large"
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        print("Loading GroundDINO model")
        self.__Build_GroundingDINO()

        if SAM == "SAM1":
            print("SAM1 selected: a versatile model for object segmentation in images.")
            if SAM_MODEL is None:
                print(f"Warning: No SAM1 model selected. Defaulting to '{self.default_sam1}'.")
                try:
                    self.__Build_SAM1(SAM=self.default_sam1)
                except Exception as e:
                    print(f"An error occurred while loading the SAM1 model '{self.default_sam1}': {str(e)}")
            else:
                if SAM_MODEL not in SAM1_MODELS:
                    raise ValueError(f"The selected SAM model '{SAM_MODEL}' does not exist. Please choose a valid model from the available options: {list(SAM1_MODELS.keys())}.")
                print(f"Notice: Loading the {SAM_MODEL} model")
                try:
                    self.__Build_SAM1(SAM=SAM_MODEL)
                except Exception as e:
                    print(f"An error occurred while loading the SAM1 model '{SAM_MODEL}': {str(e)}")
        
        elif SAM == "SAM2":
            print("SAM2 selected: optimized for images and videos, offering improved object segmentation performance.")
            if SAM_MODEL is None:
                print(f"Warning: No SAM2 model selected. Defaulting to '{self.default_sam2}'")
                try:
                    self.__Build_SAM2(SAM=self.default_sam2)
                except Exception as e:
                    print(f"An error occurred while loading the SAM2 model '{self.default_sam2}': {str(e)}")
            else:
                if SAM_MODEL not in SAM2_MODELS:
                    raise ValueError(f"The selected SAM model '{SAM_MODEL}' does not exist. Please choose a valid model from the available options: {list(SAM2_MODELS.keys())}.")
                print(f"Notice: Loading the {SAM_MODEL} model")
                try:
                    self.__Build_SAM2(SAM=SAM_MODEL)
                except Exception as e:
                    print(f"An error occurred while loading the SAM2 model '{SAM_MODEL}': {str(e)}")


    def __Build_GroundingDINO(self,):
        """
            Build the Grounding DINO model.
        """
        repo_id = "ShilongLiu/GroundingDINO"
        filename = "groundingdino_swint_ogc.pth"
        cache_config = "GroundingDINO_SwinT_OGC.cfg.py"
        try:
            cache_config_file = hf_hub_download(repo_id=repo_id, filename=cache_config)
            pth_file = hf_hub_download(repo_id=repo_id, filename=filename)
        except:
            raise RuntimeError(f"Error downloading GroundingDINO model. Please ensure that the {repo_id}/{cache_config} file exists and the {filename} checkpoint is functional.")
        
        try:
            self.groundingdino = load_model(cache_config_file,pth_file, device=self.device)
        except Exception as e:
            raise RuntimeError(f"An error occurred while loading the GroundingDINO model: {str(e)}")


    
    def __Build_SAM1(self,
                     SAM:str,) -> None:
        """
            Build the SAM1 model.

            Args:
                SAM (str): The name of the SAM model to build.
        """
        try:
            checkpoint_url = SAM1_MODELS[SAM1]
            sam = sam_model_registry[SAM]()
            state_dict = torch.hub.load_state_dict_from_url(checkpoint_url)
        except Exception as e:
            raise RuntimeError(f"Error downloading SAM. Please ensure the model is correct: {SAM} and that the checkpoint is functional: {checkpoint_url}.")
        try:
            sam.load_state_dict(state_dict, strict=True)
            sam.to(device=self.device)
            self.SAM1 = SamPredictor(sam)
        except Exception as e:
            raise RuntimeError(f"SAM1 model can't be compile: {str(e)}")




    def __Build_SAM2(self,
                     SAM:str) -> None:
        """
            Build the SAM2 model.

            Args:
                SAM (str): The name of the SAM model to build.
        """
        pass

    def predict_dino(self, 
                     image: Union[Image.Image, 
                                  torch.Tensor, 
                                  np.ndarray], 
                     text_prompt: str, 
                     box_threshold: float, 
                     text_threshold: float,
                     Normalize:bool = False,) -> torch.Tensor:
        """
            Run the Grounding DINO model for bounding box prediction.

            Args:
                image (Union[Image.Image, torch.Tensor, np.ndarray]): The input image with (WxHxC) shape.
                text_prompt (str): The text prompt for bounding box prediction.
                box_threshold (float): The threshold for bounding box prediction.
                text_threshold (float): The threshold for text prediction.
                Normalize (bool, optional): Whether to normalize the image. Defaults to False.

            Returns:
                torch.Tensor: The predicted bounding boxes with (B,4) shape with logits and phrases.
        """
        image_trans = load_trans_image(image)
        image_array = change_image_instance(image)
        boxes, logits, phrases = predict(model=self.groundingdino,
                                         image=image_trans,
                                         caption=text_prompt,
                                         box_threshold=box_threshold,
                                         text_threshold=text_threshold,
                                         device=self.device)
        if Normalize:
            W, H = image_array.shape[:2]
            boxes = box_ops.box_cxcywh_to_xyxy(boxes) * torch.Tensor([W, H, W, H])

        boxes,logits,phrases = postprocess_box(boxes,logits,phrases)
        return boxes, logits, phrases
    
    def predict_dino_batch(self,
                           images:List[Union[Image.Image,torch.Tensor,np.ndarray]],
                           text_prompt: str, 
                           box_threshold: float, 
                           text_threshold: float,
                           Normalize:bool = False,) -> Tuple[List[torch.Tensor],List[torch.Tensor],List[torch.Tensor]]:
        """
            Run the Grounding DINO model for batch prediction.

            Args:
                images (List[Union[Image.Image, torch.Tensor, np.ndarray]]): The input images with (WxHxC) shape.
                text_prompt (str): The text prompt for bounding box prediction.
                box_threshold (float): The threshold for bounding box prediction.
                text_threshold (float): The threshold for text prediction.
                Normalize (bool, optional): Whether to normalize the image. Defaults to False

            Returns:
                Tuple[List[torch.Tensor],List[torch.Tensor],List[torch.Tensor]]: The predicted bounding boxes with (B,4) shape with logits and phrases.
        """
        results = list(map(lambda image: self.predict_dino(image=image,
                                                           text_prompt=text_prompt,
                                                           box_threshold=box_threshold,
                                                           text_threshold=text_threshold,
                                                           Normalize=Normalize), images))
    
        boxes, logits, phrases = zip(*results)
        return list(boxes), list(logits), list(phrases)
    
    def predict_SAM1(self,
                    image: Union[Image.Image, 
                                 torch.Tensor,
                                 np.ndarray], 
                    boxes: Optional[torch.Tensor] = None,
                    points_coords: Optional[torch.Tensor] = None,
                    points_labels: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
            Run the SAM1 model for image segmentation.

            Args:
                image (Union[Image.Image, torch.Tensor, np.ndarray]): The input image with (WxHxC) shape.
                boxes (Optional[torch.Tensor], optional): The bounding boxes for segmentation. Defaults to None.
                points_coords (Optional[torch.Tensor], optional): The coordinates of the points for segmentation. Defaults to None.
                points_labels (Optional[torch.Tensor], optional): The labels of the points for segmentation. Defaults to None.

            Returns
                torch.Tensor: The predicted segmentation mask with (WxHx1) shape.
    """
        image_array = change_image_instance(image)
        transformed_boxes,transformed_points,points_labels = self.__prep_prompts(boxes,
                                                                                 points_coords,
                                                                                 points_labels,
                                                                                 image_array.shape[:2])

        self.SAM1.set_image(image_array)
        masks, _, _ = self.SAM1.predict_torch(point_coords=transformed_points.to(self.SAM1.device),
                                              point_labels=points_labels.to(self.SAM1.device),
                                              boxes=transformed_boxes.to(self.SAM1.device),
                                              multimask_output=False,
        )
        self.SAM1.reset_image()
        masks = postprocess_masks(masks=masks,
                              area_threshold=500)
        masks = masks.cpu()
        mask = torch.any(masks,dim=0).permute(1,2,0).numpy()
        return mask
    
    def predict_SAM1_batch(self,
                           images:List[Union[Image.Image,
                                             torch.Tensor,
                                             np.ndarray]],
                           boxes:Optional[List[torch.Tensor]] = None,
                           points_coords:Optional[List[torch.Tensor]] = None,
                           points_labels:Optional[List[torch.Tensor]] = None) -> List[torch.Tensor]:
        """
            Run the SAM1 model for batch prediction.

            Args:
                images (List[Union[Image.Image, torch.Tensor, np.ndarray]]): The input images with (WxHxC) shape.
                boxes (Optional[List[Optional[torch.Tensor]]]): List of bounding boxes for each image. Can be None.
                points_coords (Optional[List[Optional[torch.Tensor]]]): List of point coordinates for each image. Can be None.
                points_labels (Optional[List[Optional[torch.Tensor]]]): List of point labels for each image. Can be None.

            Returns:
                List[np.ndarray]: The predicted masks for each image.
        """
        if points_coords is not None and points_labels is None:
            raise ValueError("If 'points_coords' is provided, 'points_labels' must also be provided, and vice versa.")
        elif points_labels is not None and points_coords is None:
            raise ValueError("If 'points_labels' is provided, 'points_coords' must also be provided, and vice versa.")

        if boxes is None:
            boxes = [None] * len(images)
        if points_coords is None:
            points_coords = [None] * len(images)
            points_labels = [None] * len(images)

        if not (len(images) == len(boxes) == len(points_coords) == len(points_labels)):
            raise ValueError("The lengths of 'images', 'boxes', 'points_coords', and 'points_labels' must match.")
        
        def process_image(image: Union[Image.Image,torch.Tensor,np.ndarray],
                          box: Optional[torch.Tensor],
                          point_coord: Optional[torch.Tensor],
                          point_label: Optional[torch.Tensor]) -> torch.Tensor:
            """
                Process a single image with its corresponding boxes and points.

                Args:
                    image (Union[Image.Image,torch.Tensor,np.ndarray]): The input image with (WxHxC) shape.
                    box (Optional[torch.Tensor]): The bounding boxes for the image.
                    point_coords (Optional[torch.Tensor]): The point coordinates for the image.
                    point_labels (Optional[torch.Tensor]): The point labels for the image.

                Returns:
                    np.ndarray: The predicted mask for the image.
            """
            transformed_boxes, transformed_points, points_labels = self.__prep_prompts(box,point_coord,point_label)
            image = change_image_instance(image)
            self.SAM1.set_image()
            #POSIBLE ERROR NONE.TO  CUDA??????
            masks, _, _ = self.SAM1.predict_torch(point_coords=transformed_points.to(self.SAM1.device),
                                                  point_labels=points_labels.to(self.SAM1.device),
                                                  boxes=transformed_boxes.to(self.SAM1.device),
                                                  multimask_output=False)
            self.SAM1.reset_image()
            masks = postprocess_masks(masks=masks, area_threshold=500)
            masks = masks.cpu()
            mask = torch.any(masks, dim=0).permute(1, 2, 0).numpy()
            return mask
        results = [process_image(image, box, point_coords, point_labels) for image, box, point_coords, point_labels in zip(images, boxes, points_coords, points_labels)]
        return results

    #def predict
    #def predict_batch
    def predict_batch(self,
                      image,
                      text_prompt,
                      box_threshold,
                      process_box_threshold,
                      text_threshold,
                      mode_predict) -> torch.Tensor:
                
        boxes, logits, phrases = self.predict_dino(image=image,
                                                   text_prompt=text_prompt,
                                                   box_threshold=box_threshold,
                                                   text_threshold=text_threshold)
        image_array = change_image_instance(image)
        shape = image_array.shape[:2]
        boxes = [boxes]
        logits = [logits]
        phrases = [phrases]
        new_boxes, new_logits, new_phrases = process_box_batch(shape=shape, 
                                                               boxes=boxes,
                                                               logits=logits,
                                                               phrases=phrases,
                                                               box_threshold=process_box_threshold)
        if mode_predict == 'box_predict':
            masks = self.predict_sam_with_boxes(image=image,
                                                boxes=new_boxes)
            masks = torch.any(masks,dim=0).permute(1,2,0).numpy()

        return new_boxes, new_logits, new_phrases, masks
    def LangSam_batch(self,
                image_data: torch.Tensor,
                text_prompt: str,
                box_threshold: float,
                process_box_threshold: float,
                text_threshold: float,
                mode_predict: str,
                mode_data: str) -> torch.Tensor:
        
        boxess = []
        logitss = []
        phrasess = []
        images = []
        ids = []
        original_masks = []
        predict_masks = []
        for data in image_data:
            for i in range(len(data[0])):
                image = data[0][i]
                mask_org = data[1][i]
                id = data[2][i]
                image_source = np.asarray(image)
        
                if mode_data == 'batch':
                    boxes, logits, phrases, masks= self.predict_batch(image=image,
                                                                      text_prompt=text_prompt,
                                                                      box_threshold=box_threshold,
                                                                      process_box_threshold=process_box_threshold,
                                                                      text_threshold=text_threshold,
                                                                      mode_predict=mode_predict)
                    
                boxess.append(boxes)
                logitss.append(logits)
                phrasess.append(phrases)
                images.append(image_source)
                original_masks.append(mask_org)
                ids.append(id)
                predict_masks.append(masks)

        images = np.asarray(images)
        ids = np.asarray(ids)
        original_masks = np.asarray(original_masks)
        predict_masks = np.asarray(predict_masks)
        return boxess,logitss,phrasess,images,ids,original_masks, predict_masks

    def reset_model(self):
        self.sam.reset_image()

    @property
    def device(self):
        return self.device
    
    def __prep_prompts(self,boxes,points_coords,points_labels,dims):
        W,H = dims
        if boxes is not None:
            clip_valor = np.clip(boxes[0][0], 0, 1)
            if clip_valor == boxes[0][0]:
                boxes = box_ops.box_cxcywh_to_xyxy(boxes) * torch.Tensor([W,H,W,H])
                transformed_boxes = self.SAM1.transform.apply_boxes_torch(boxes, (W,H))
        else:
            transformed_boxes=None

        if points_coords is not None and points_labels is None:
            raise ValueError("If 'points_coords' is provided, 'points_labels' must also be provided, and vice versa.")
        elif points_labels is not None and points_coords is None:
            raise ValueError("If 'points_labels' is provided, 'points_coords' must also be provided, and vice versa.")
        elif points_coords is not None and points_labels is not None:
            transformed_points = self.SAM1.transform.apply_coords_torch(points_coords, (W,H))
        else:
             transformed_points = None
             points_labels = None
    
        return transformed_boxes,transformed_points,points_labels
        
        
        
if __name__ == "__main__":
    from groundino_samnet.utils import load_trans_image, change_image_instance, process_box_batch, process_masks
    SAM1 = GSamNetwork(SAM="SAM1",SAM_MODEL="sa")
else:
    from .utils import load_trans_image, change_image_instance, process_box_batch, process_masks