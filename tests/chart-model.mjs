import assert from 'node:assert/strict';
import {chartPaths} from '../custom_components/r290_heatpump/frontend/model.js';
import {compatibleUnit} from '../custom_components/r290_heatpump/frontend/chart-ui.js';
assert.equal(chartPaths([[0,10],[20,null],[40,20],[60,30]],0,100,0,40,148,78),'M32.0,42.0H52.0M72.0,32.0H92.0V22.0H132.0');
assert.equal(chartPaths([[0,10],[120,null]],0,100,0,40,148,78),'M32.0,42.0H132.0');
assert.equal(chartPaths([[0,null],[20,null]],0,100,0,40,148,78),'');
assert.equal(compatibleUnit('°F','°C'),true);assert.equal(compatibleUnit('K','°C'),true);assert.equal(compatibleUnit('kW','W'),true);assert.equal(compatibleUnit('kWh','W'),false);
console.log('PASS chart steps match tooltip state intervals, gaps stay blank and source units remain compatible');
