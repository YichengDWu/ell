"""
The core declarative functionality of the ell language model programming library.
"""

# This isn't fully accurate because we should enable the user to apply images and other multimodal inputs but we can address this now.
from collections import defaultdict
from functools import wraps
import hashlib
import json
import time
import ell.util.closure
import colorama
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union, cast
from ell.configurator import  config
from ell.lstr import lstr
from ell.types import LMP, InvocableLM, LMPParams, Message, MessageOrDict, _lstr_generic
from ell.util.verbosity import  model_usage_logger_post_end, model_usage_logger_post_intermediate, model_usage_logger_post_start, model_usage_logger_pre, compute_color
import numpy as np
import openai


import logging
colorama.Style


logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = "You are a helpful AI assistant."
DEFAULT_LM_PARAMS: Dict[str, Any] = dict()


def _get_messages(res: Union[str, list[MessageOrDict]], fn: LMP) -> list[Message]:
    """
    Helper function to convert the output of an LMP into a list of Messages.
    """
    if isinstance(res, str):
        return [
            Message(role="system", content=(fn.__doc__) or DEFAULT_SYSTEM_PROMPT),
            Message(role="user", content=res),
        ]
    else:
        assert isinstance(
            res, list
        ), "Need to pass a list of MessagesOrDict to the language model"
        return res


def _get_lm_kwargs(lm_kwargs: Dict[str, Any], lm_params: LMPParams) -> Dict[str, Any]:
    """
    Helper function to combine the default LM parameters with the provided LM parameters and the parameters passed to the LMP.
    """
    final_lm_kwargs = dict(**DEFAULT_LM_PARAMS)
    final_lm_kwargs.update(**lm_kwargs)
    final_lm_kwargs.update(**lm_params)
    return final_lm_kwargs


def _run_lm(
    model: str,
    messages: list[Message],
    lm_kwargs: Dict[str, Any],
    client: Optional[openai.Client] = None,
    lmp_orginator="NOT IMPLEMENTED",
    _logging_color=None,
) -> Union[lstr, Iterable[lstr]]:
    """
    Helper function to run the language model with the provided messages and parameters.
    """
    # Todo: Decide if the client specified via the context amanger default registry is the shit or if the cliennt specified via lmp invocation args are the hing.
    client =   client or config.get_client_for(model)
    if client is None:
        raise ValueError(f"No client found for model '{model}'. Ensure the model is registered using 'register_model' in 'config.py' or specify a client directly using the 'client' argument in the decorator or function call.")
    
    model_result = client.chat.completions.create(
        model=model, messages=messages, stream=True, **lm_kwargs
    )

    
    choices_progress = defaultdict(list)
    n = lm_kwargs.get("n", 1)

    if config.verbose:
        model_usage_logger_post_start(_logging_color, n)

    with model_usage_logger_post_intermediate(_logging_color, n) as _logger:
        for chunk in model_result:
            for choice in chunk.choices:
                # print(choice)
                choices_progress[choice.index].append(choice)
                if config.verbose and choice.index == 0:
                    _logger(choice.delta.content)

    if config.verbose:
        model_usage_logger_post_end()
    n_choices = len(choices_progress)

    tracked_results = [
        lstr(
            content="".join((choice.delta.content or "" for choice in choice_deltas)),
            # logits=( #
            #     np.concatenate([np.array(
            #         [c.logprob for c in choice.logprobs.content or []]
            #     ) for choice in choice_deltas])  # mypy type hinting is dogshit.
            # ),
            # Todo: Properly implement log probs.
            originator=lmp_orginator,
        )
        for _, choice_deltas in sorted(choices_progress.items(), key= lambda x: x[0],)
    ]

    return tracked_results[0] if n_choices == 1 else tracked_results



def lm(model: str, client: Optional[openai.Client] = None, **lm_kwargs):
    """
    Defines a basic language model program (a parameterization of an existing foundation model using a particular prompt.)

    This is a decorator that can be applied to any LMP type.
    """
    default_client_from_decorator = client 

    def decorator(
        fn: LMP,
    ) -> InvocableLM:
        color = compute_color(fn)

        @wraps(fn)
        def wrapper(
            *fn_args,
            client: Optional[openai.Client] = None,
            lm_params: LMPParams = {},
            invocation_kwargs=False,
            **fn_kwargs,
        ) -> _lstr_generic:
            res = fn(*fn_args, **fn_kwargs)
            
            messages = _get_messages(res, fn)
            if config.verbose: model_usage_logger_pre(fn, fn_args, fn_kwargs, "notimplemented", messages, color)
            final_lm_kwargs = _get_lm_kwargs(lm_kwargs, lm_params)
            _invocation_kwargs = dict(model=model, messages=messages, lm_kwargs=final_lm_kwargs, client=client or default_client_from_decorator, _logging_color=color)
            tracked_str = _run_lm(**_invocation_kwargs)
            return tracked_str, _invocation_kwargs

        # TODO: # we'll deal with type safety here later
        wrapper.__ell_lm_kwargs__ = lm_kwargs
        wrapper.__ell_func__ = fn
        return track(wrapper)

    return decorator


def track(fn: Callable) -> Callable:
    if hasattr(fn, "__ell_lm_kwargs__"):
        func_to_track = fn
        lm_kwargs = fn.__ell_lm_kwargs__
        lmp = True
    else:
        func_to_track = fn
        lm_kwargs = None
        lmp = False


    # see if it exists
    _name = func_to_track.__qualname__
    _time = time.time()
    _has_serialized = False
    

    @wraps(fn)
    def wrapper(*fn_args, get_invocation=False, **fn_kwargs) -> str:
        nonlocal _has_serialized
        assert (get_invocation and config.has_serializers) or not get_invocation, "In order to get an invocation, you must have a serializer and get_invocation must be True."
        # get the prompt
        (result, invocation_kwargs) = (
            (fn(*fn_args, **fn_kwargs), None)
            if not lmp
            else fn(*fn_args, **fn_kwargs)
            )
            
            
        if config.has_serializers and not _has_serialized:
            fn_closure, _uses = ell.util.closure.lexically_closured_source(func_to_track)
            fn_hash = func_to_track.__ell_hash__
            # print(fn_hash)
            

            for serializer in config.serializers:
                serializer.write_lmp(
                    lmp_id=fn_hash,
                    name=_name,
                    source=fn_closure[0],
                    dependencies=fn_closure[1],
                    created_at=_time,
                    is_lmp=lmp,
                    lm_kwargs=(
                        json.dumps(lm_kwargs)
                        if lm_kwargs
                        else None
                    ),
                    uses=_uses,
                )
            _has_serialized = True

            # Let's add an invocation
            invocation_params = dict(
                lmp_id=fn_hash,
                args=json.dumps(fn_args),
                kwargs=json.dumps(fn_kwargs),
                result=json.dumps(result),
                created_at=time.time(),
                invocation_kwargs=invocation_kwargs,
            )
            
            for serializer in config.serializers:
                serializer.write_invocation(**invocation_params)
            
            invoc = invocation_params  # For compatibility with existing code

        if get_invocation:
            return result, invoc
        else:
            return result

    fn.__wrapper__ = wrapper
    wrapper.__ell_lm_kwargs__ = lm_kwargs
    wrapper.__ell_func__ = func_to_track




    return wrapper


