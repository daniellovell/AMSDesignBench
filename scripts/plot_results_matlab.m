function plot_results_matlab(resultsPath)
% plot_results_matlab - Interactive MATLAB plots for eval results
%
% Usage:
%   - From MATLAB: run scripts/plot_results_matlab
%   - Optionally:  plot_results_matlab('/abs/path/to/combined_results.jsonl')
%
% Behavior:
%   - Opens a file dialog defaulting to the latest results (you can change it)
%   - Loads combined_results.jsonl (one JSON object per line)
%   - Generates the same plots as harness/reporting/plots.py:
%       1) Heatmap: Judge score heatmap (model × modality)
%       2) Grouped bars per family: models × modality (judge avg)
%   - Does NOT save figures. They are opened interactively for editing.
%
% Notes:
%   - Expects records with fields: model, modality, topic/family, judge.overall
%   - Modality labels follow Python: spice_netlist→SPICE, casIR→casIR, cascode→ADL
%   - This script is self-contained and requires base MATLAB with jsondecode.

  % ---------------- Global figure formatting (tweak as desired) ----------------
  CFG = struct();
  CFG.fontName              = 'Times';       % Global font - professional for papers
  CFG.baseFontSize          = 16;            % Axes tick font size
  CFG.titleFontSize         = 16;            % Title font size
  CFG.labelFontSize         = 16;            % Axis label font size
  CFG.legendFontSize        = 16;            % Legend font size
  CFG.figureBG              = 'w';           % Figure background color
  CFG.colormap              = 'viridis';     % Colormap for heatmap (fallbacks if missing)
  CFG.grid                   = 'off';         % 'on' or 'off' - off for cleaner bar charts
  CFG.legendLocation        = 'best';        % Legend location
  CFG.rotateXTick           = 0;             % Degrees - no rotation to prevent subscript issues
  CFG.barFaceAlpha          = 0.95;          % 0..1 transparency for bars
  CFG.figWidthPerModelPx    = 180;           % Width per model for grouped bars (pixels) - increased for better spacing
  CFG.figMinWidthPx         = 640;           % Minimum figure width
  CFG.figHeightPx           = 480;           % Figure height for grouped bars (pixels) - increased for text labels

  % -----------------------------------------------------------------------------

  if nargin < 1 || isempty(resultsPath)
    resultsPath = '';
  end

  % Determine default (latest) results path
  try
    repoRoot = fileparts(fileparts(mfilename('fullpath'))); % scripts/ -> repo root
  catch
    repoRoot = pwd();
  end
  defaultPath = findLatestResults(repoRoot);

  % If user didn't supply path, ask via file dialog with latest preselected
  if isempty(resultsPath)
    if isempty(defaultPath)
      startDir = fullfile(repoRoot, 'outputs');
      [fname, fpath] = uigetfile('*.jsonl', 'Select combined_results.jsonl', startDir);
    else
      [fname, fpath] = uigetfile('*.jsonl', 'Select combined_results.jsonl', defaultPath);
    end
    if isequal(fname, 0)
      fprintf('Cancelled. No file selected.\n');
      return;
    end
    resultsPath = fullfile(fpath, fname);
  end

  if ~isfile(resultsPath)
    error('Results not found: %s', resultsPath);
  end
  fprintf('[matlab-plots] Using results: %s\n', resultsPath);

  % Load JSONL records
  recs = load_jsonl(resultsPath);
  if isempty(recs)
    error('No records found in %s', resultsPath);
  end

  % Aggregate judge.overall by (model, modality, family)
  data = containers.Map('KeyType','char','ValueType','any');
  modelsSet = string.empty(1,0);
  modalitiesSet = string.empty(1,0);
  familiesSet = string.empty(1,0);

  for i = 1:numel(recs)
    r = recs{i};
    if ~isfield(r, 'judge') || ~isstruct(r.judge) || ~isfield(r.judge, 'overall')
      continue
    end
    sc = r.judge.overall;
    if ~isnumeric(sc) || ~isfinite(sc)
      continue
    end
    model = fieldOr(r, 'model', '?');
    mod0  = fieldOr(r, 'modality', '?');
    modal = modality_label(mod0);
    fam   = fieldOr(r, 'topic', '');
    if isempty(fam)
      fam = fieldOr(r, 'family', '?');
    end
    modelsSet = unique([modelsSet string(model)]);
    modalitiesSet = unique([modalitiesSet string(modal)]);
    familiesSet = unique([familiesSet string(fam)]);

    key = join([string(model), string(modal), string(fam)], '||');
    if isKey(data, key)
      v = data(key);
      v.sum = v.sum + double(sc);
      v.n = v.n + 1;
      data(key) = v;
    else
      data(key) = struct('sum', double(sc), 'n', 1);
    end
  end

  % Sort for stable plotting
  models = sort(modelsSet);
  % Custom order for modalities: SPICE, casIR, Cascode ADL
  modalityOrder = ["SPICE", "casIR", "Cascode ADL"];
  modalities = modalityOrder(ismember(modalityOrder, modalitiesSet));
  % Add any other modalities not in our predefined order
  otherModalities = modalitiesSet(~ismember(modalitiesSet, modalityOrder));
  modalities = [modalities, sort(otherModalities)];
  families = sort(familiesSet);

  % Precompute shorter labels for models (used in heatmap and bars)
  modelLabelsShort = cellstr(models);
  for k = 1:length(modelLabelsShort)
    lbl = modelLabelsShort{k};
    lbl = strtrim(lbl);
    lbl = regexprep(lbl, '^(anthropic|openai|openrouter)[-_:]', '');
    % Drop trailing "-latest" or "_latest"
    lbl = regexprep(lbl, '[-_]?latest$', '');
    lbl = strrep(lbl, '_', '-');
    modelLabelsShort{k} = lbl;
  end

  % 1) Heatmap: aggregate across families → (model, modality)
  mm = containers.Map('KeyType','char','ValueType','any');
  keys = data.keys;
  for i = 1:numel(keys)
    parts = split(string(keys{i}), '||');
    model = parts(1); modal = parts(2);
    k2 = join([model, modal], '||');
    v = data(keys{i});
    if isKey(mm, k2)
      x = mm(k2); x.sum = x.sum + v.sum; x.n = x.n + v.n; mm(k2) = x;
    else
      mm(k2) = struct('sum', v.sum, 'n', v.n);
    end
  end

  M = numel(models); K = numel(modalities);
  mat = nan(M, K);
  for ii = 1:M
    for jj = 1:K
      k2 = join([models(ii), modalities(jj)], '||');
      if isKey(mm, k2)
        v = mm(k2);
        if v.n > 0
          mat(ii, jj) = v.sum / v.n;
        end
      end
    end
  end

  % Create heatmap figure
  fig = figure('Name','Judge score heatmap (model × modality)', 'NumberTitle','off', 'Color', CFG.figureBG);
  ax = axes('Parent', fig);
  imagesc(ax, mat, [0 1]);
  colormap(ax, pickColormap(CFG.colormap));
  colorbar(ax, 'Location','eastoutside');
  set(ax, 'XTick', 1:K, 'XTickLabel', cellstr(modalities));
  set(ax, 'YTick', 1:M, 'YTickLabel', modelLabelsShort);
  set(ax, 'TickLabelInterpreter', 'none');
  xtickangle(ax, CFG.rotateXTick);
  title(ax, 'Judge score heatmap (model × modality)', 'FontName', CFG.fontName, 'FontSize', CFG.titleFontSize);
  ylabel(ax, 'Model', 'FontName', CFG.fontName, 'FontSize', CFG.labelFontSize);
  xlabel(ax, 'Modality', 'FontName', CFG.fontName, 'FontSize', CFG.labelFontSize);
  set(ax, 'FontName', CFG.fontName, 'FontSize', CFG.baseFontSize, 'Box','on', 'Layer','top', 'GridColor',[0.8 0.8 0.8]);
  grid(ax, CFG.grid);
  axis(ax, 'tight');

  % 2) Grouped bars per family
  for ff = 1:numel(families)
    fam = families(ff);
    Y = nan(M, K);
    for ii = 1:M
      for jj = 1:K
        k = join([models(ii), modalities(jj), fam], '||');
        if isKey(data, k)
          v = data(k);
          if v.n > 0
            Y(ii, jj) = v.sum / v.n;
          end
        end
      end
    end

    % Figure sizing proportional to number of models
    widthPx = max(CFG.figMinWidthPx, CFG.figWidthPerModelPx * max(1, M));
    heightPx = CFG.figHeightPx;

    fig2 = figure('Name', sprintf('Grouped bars - %s', fam), 'NumberTitle','off', ...
                  'Color', CFG.figureBG, 'Position', [100 100 widthPx heightPx]);
    ax2 = axes('Parent', fig2);
    hb = bar(ax2, Y, 'grouped');
    % Apply bar aesthetics
    for jj = 1:numel(hb)
      hb(jj).FaceAlpha = CFG.barFaceAlpha;
      hb(jj).EdgeColor = 'none';
    end
    
    % Add score labels on top of bars
    for ii = 1:M  % for each model
      for jj = 1:K  % for each modality
        if ~isnan(Y(ii, jj))
          % Get bar position
          x_offset = (jj - (K+1)/2) * 0.8/K;  % grouped bar spacing
          x_pos = ii + x_offset;
          y_pos = Y(ii, jj) + 0.02;  % slightly above bar
          
          % Format score to 2 decimal places
          scoreText = sprintf('%.2f', Y(ii, jj));
          text(ax2, x_pos, y_pos, scoreText, 'HorizontalAlignment', 'center', ...
               'VerticalAlignment', 'bottom', 'FontSize', CFG.baseFontSize-1, ...
               'FontName', CFG.fontName, 'FontWeight', 'normal');
        end
      end
    end
    % Fix x-axis labels to prevent subscript rendering
    modelLabels = modelLabelsShort;
    set(ax2, 'XTick', 1:M, 'XTickLabel', modelLabels);
    set(ax2, 'TickLabelInterpreter', 'none');
    xtickangle(ax2, CFG.rotateXTick);
    ylim(ax2, [0 1.15]);  % Extra space for score labels on top
    ylabel(ax2, 'Judge score', 'FontName', CFG.fontName, 'FontSize', CFG.labelFontSize);
    title(ax2, sprintf('%s: models × modality (judge avg)', fam), 'FontName', CFG.fontName, 'FontSize', CFG.titleFontSize);
    legend(ax2, cellstr(modalities), 'Location', CFG.legendLocation, 'FontSize', CFG.legendFontSize);
    set(ax2, 'FontName', CFG.fontName, 'FontSize', CFG.baseFontSize, 'Box','on', 'Layer','top');
    grid(ax2, CFG.grid);
    % Don't use axis tight to preserve our custom ylim for text labels
    xlim(ax2, [0.5 M+0.5]);
  end
end

% ------------------------------- Helpers ------------------------------------
function out = fieldOr(s, name, default)
  if isstruct(s) && isfield(s, name) && ~isempty(s.(name))
    out = s.(name);
  else
    out = default;
  end
end

function recs = load_jsonl(path)
  recs = {};
  fid = fopen(path, 'r');
  if fid < 0
    error('Failed to open %s', path);
  end
  cleaner = onCleanup(@() fclose(fid));
  while true
    tline = fgetl(fid);
    if ~ischar(tline), break; end
    tline = strtrim(tline);
    if isempty(tline), continue; end
    try
      rec = jsondecode(tline);
      recs{end+1} = rec; %#ok<AGROW>
    catch %#ok<CTCH>
      % Skip invalid JSON lines silently (consistent with Python)
    end
  end
end

function label = modality_label(m)
  m = string(strtrim(string(m)));
  switch lower(m)
    case 'spice_netlist'
      label = "SPICE";
    case 'cascode'
      label = "Cascode ADL";
    case 'casir'
      label = "casIR";
    otherwise
      if strlength(m) == 0
        label = "?";
      else
        label = m;
      end
  end
end

function path = findLatestResults(repoRoot)
  % Prefer outputs/latest/results.jsonl
  p1 = fullfile(repoRoot, 'outputs', 'latest', 'results.jsonl');
  if isfile(p1), path = p1; return; end
  % Next: outputs/latest/combined_results.jsonl
  p2 = fullfile(repoRoot, 'outputs', 'latest', 'combined_results.jsonl');
  if isfile(p2), path = p2; return; end
  % Fallback: newest outputs/run_*/combined_results.jsonl
  runsDir = fullfile(repoRoot, 'outputs');
  dd = dir(fullfile(runsDir, 'run_*'));
  newestPath = '';
  newestDtnum = -inf;
  for i = 1:numel(dd)
    if dd(i).isdir
      cand = fullfile(dd(i).folder, dd(i).name, 'combined_results.jsonl');
      if isfile(cand)
        info = dir(cand);
        if info.datenum > newestDtnum
          newestDtnum = info.datenum;
          newestPath = cand;
        end
      end
    end
  end
  if ~isempty(newestPath)
    path = newestPath; return;
  end
  % None found
  path = '';
end

function cmap = pickColormap(name)
  % Try to pick a perceptually-uniform colormap; fallback to parula
  if nargin < 1 || isempty(name)
    name = 'parula';
  end
  name = lower(string(name));
  try
    switch name
      case "viridis"
        cmap = viridis();
      case "parula"
        cmap = parula;
      case {"turbo", "jet"}
        cmap = turbo;
      otherwise
        cmap = parula;
    end
  catch
    cmap = parula;
  end
end

function cmap = viridis()
  % Minimal viridis fallback if MATLAB doesn't have it
  try
    cmap = colormap('viridis');
  catch
    cmap = [...
      0.2670 0.0049 0.3294
      0.2823 0.0940 0.4185
      0.2832 0.1688 0.4693
      0.2763 0.2305 0.4964
      0.2637 0.2858 0.5141
      0.2470 0.3367 0.5253
      0.2270 0.3850 0.5311
      0.2040 0.4314 0.5331
      0.1786 0.4764 0.5316
      0.1510 0.5208 0.5276
      0.1223 0.5646 0.5210
      0.0938 0.6079 0.5121
      0.0661 0.6506 0.5009
      0.0403 0.6926 0.4877
      0.0180 0.7339 0.4727
      0.0046 0.7745 0.4560
      0.0060 0.8144 0.4377
      0.0272 0.8535 0.4180
      0.0689 0.8918 0.3970
      0.1309 0.9293 0.3747
    ];
  end
end

