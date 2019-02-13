from flask import Blueprint, render_template, request, session, jsonify, current_app, g, url_for, \
    abort

from .forms import TranslateForm
from ..logging_utils import logged
from ..model_settings import model2problem, get_models, get_default_model_name, get_model_names,\
    model2server, get_model_list, get_possible_directions

from app.main.translate import translate_with_model

bp = Blueprint('main', __name__)


def _translate_from_to(source, target, text):
    models_on_path = get_model_list(source, target)
    translation = []
    for cfg in models_on_path:
        translation = translate_with_model(cfg['model'], text)
        text = ' '.join(translation).replace('\n ', '\n')
    return translation


@bp.route('/', methods=['GET'])
def index():
    if _request_wants_json():
        return api_index()
    form = TranslateForm()
    choices = get_src_tgt_choices()
    form.lang_pair.choices = choices
    form.lang_pair.default = choices[0][0]
    form.models.choices = url_for_choices()
    form.models.default = form.models.choices[0][0]
    return render_template('index.html', form=form,
                           file_size_limit=current_app.config['MAX_CONTENT_LENGTH'])


def url_for_src_tgt(source, target):
    return url_for('main.source_target_translate') + '?src={}&tgt={}'.format(source, target)


def get_src_tgt_choices():
    return list(map(lambda tuple3: (url_for_src_tgt(tuple3[0], tuple3[1]), tuple3[2]),
                    get_possible_directions()))


@bp.route('/docs', methods=['GET'])
def docs():
    return render_template('docs.html', file_size_limit=current_app.config['MAX_CONTENT_LENGTH'])


def url_for_choices():
    return list(map(lambda cfg:
                    (url_for('main.run_task', model=cfg['model']), cfg['title']), get_models()))


def _request_wants_json():
    best = request.accept_mimetypes \
        .best_match(['application/json', 'text/html'])
    return best == 'application/json' and \
        request.accept_mimetypes[best] > \
        request.accept_mimetypes['text/html']


@bp.route('/api', methods=['GET'])
def api_index():
    return jsonify({
        '_links': {
            'self': {'href': url_for('main.api_index')},
            'versions': [{'href': url_for('main.api_index_v1'), 'title': 'Version 1'}],
            'latest': {'href': url_for('main.api_index_v1'), 'title': 'Version 1'}
        },
        '_embedded': {
            'latest': index_v1()
        }
    })


@bp.route('/api/v1')
def api_index_v1():
    return jsonify(index_v1())


def index_v1():
    return {
        '_links': {
            'self': {'href': url_for('main.api_index_v1')},
            'models': {'href': url_for('main.api_models_v1')},
            'languages': {'href': url_for('main.api_languages_v1')}
        },
        '_embedded': {
            'models': models(),
            'languages': languages()
        }
    }


@bp.route('/api/v1/models', methods=['GET'])
def api_models_v1():
    return jsonify(models())


def _get_models_with_href(supplied_models=None):
    if not supplied_models:
        supplied_models = get_models()
    models_cfg = []
    for cfg in supplied_models:
        copied = dict(cfg)
        copied['href'] = url_for('main.run_task', model=cfg['model'])
        models_cfg.append(copied)
    return models_cfg


def models():
    return {
        '_links': {
            'self': url_for('main.api_models_v1'),
            'models': _get_models_with_href()
        }
    }


@bp.route('/api/v1/models/<any' + str(tuple(get_model_names())) + ':model>', methods=['POST'])
def run_task(model):
    if request.files and 'input_text' in request.files:
        input_file = request.files.get('input_text')
        if input_file.content_type != 'text/plain':
            abort(415)
        text = input_file.read().decode('utf-8')
    else:
        text = request.form.get('input_text')
    outputs = translate_with_model(model, text)
    if _request_wants_json():
        return jsonify(outputs)
    else:
        return str(outputs)


def languages():
    return {
        '_links': {
            'self': url_for('main.api_languages_v1'),
            'languages': [{'href': url_for_src_tgt(x[0], x[1]), 'title': x[2], 'source': x[0],
                           'target': x[1], 'models':
                               [{'model': m['model']} for m in get_model_list(x[0], x[1])]}
                          for x in get_possible_directions()]
        }
    }


@bp.route('/api/v1/languages', methods=['GET'])
def api_languages_v1():
    return jsonify(languages())


@bp.route('/api/v1/languages', methods=['POST'])
def source_target_translate():
    if request.files and 'input_text' in request.files:
        input_file = request.files.get('input_text')
        if input_file.content_type != 'text/plain':
            abort(415)
        text = input_file.read().decode('utf-8')
    else:
        text = request.form.get('input_text')
    src = request.args.get('src')
    tgt = request.args.get('tgt')
    outputs = _translate_from_to(src, tgt, text)
    if _request_wants_json():
        return jsonify(outputs)
    else:
        return str(outputs)

