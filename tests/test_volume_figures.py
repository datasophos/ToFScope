"""Layer figures preserve scales, coordinates, masks and thin selections."""
import unittest
import numpy as np
from signals import SignalRecipe
from volume_layers import VolumeLayer,PreviewGrid,VolumePreview
from plots import overlay_volume_plot,tiled_volume_plot


class VolumeFigureTests(unittest.TestCase):
    def fixture(self,thin=False):
        z=np.array([12.]) if thin else np.array([12.,13.]);y=x=np.array([5.,15.]);shape=(len(z),2,2)
        grid=PreviewGrid(z,y,x,(np.array([12,14]),np.array([0,2]),np.array([0,2])),True)
        a=VolumeLayer('a',SignalRecipe(intervals=((1,2),),frames=(12,13),label='first'),colorscale='Reds',opacity=.2,percentile=0)
        b=VolumeLayer('b',SignalRecipe(intervals=((3,4),),frames=(12,13),label='second'),colorscale='Blues',opacity=.4,percentile=0)
        previews=[VolumePreview(a.id,a.recipe,grid,np.arange(1,np.prod(shape)+1,dtype=float).reshape(shape),np.ones(shape),np.ones(shape)),VolumePreview(b.id,b.recipe,grid,10*np.arange(1,np.prod(shape)+1,dtype=float).reshape(shape),np.ones(shape),np.ones(shape))]
        return previews,[a,b]

    def test_overlay_and_tile_styles_and_shared_scale(self):
        previews,styles=self.fixture()
        fig=overlay_volume_plot(previews,styles,scale_mode='independent',log=False)
        self.assertEqual(len(fig.data),2);self.assertEqual(fig.data[0].opacity,.2)
        self.assertEqual(fig.data[1].name,'second');self.assertEqual(set(fig.data[0].z),{12.,13.})
        self.assertNotEqual(fig.data[0].cmax,fig.data[1].cmax)
        shared=overlay_volume_plot(previews,styles,scale_mode='shared',log=False)
        self.assertEqual(shared.data[0].cmax,shared.data[1].cmax)
        tiled=tiled_volume_plot(previews,styles,log=False)
        self.assertEqual([t.scene for t in tiled.data],['scene','scene2'])
        np.testing.assert_array_equal(fig.data[1].value,10*np.arange(1,9,dtype=float))

    def test_thin_and_zero_selections(self):
        previews,styles=self.fixture(thin=True)
        fig=overlay_volume_plot(previews,styles)
        self.assertTrue(all(t.type=='scatter3d' for t in fig.data))
        previews[0].values[:]=0
        fig=overlay_volume_plot(previews[:1],styles[:1])
        self.assertTrue(fig.layout.annotations)

    def test_controller_layers_styles_and_paging(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch,Mock
        from test_signal_recipes import make_acquisition
        from workspace import ExplorerWorkspace
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'a.h5';make_acquisition(path)
            with patch('workspace.get_plotlyjs',return_value=''),patch.object(ExplorerWorkspace,'figures',return_value={}):
                w=ExplorerWorkspace(path);w.send=Mock()
                def event(name,**payload):
                    w.handle_message(None,dict(event=name,payload=payload),None)
                    result=w.send.call_args.args[0];self.assertNotIn('error',result,result);return result['state']
                event('comparison_add',intervals=[[4,5]],frames=[1,2])
                state=event('volume_layer_add',recipe_id=w.comparisons[0]['recipe']['id'])
                self.assertEqual(len(state['volume_layers']),2)
                identifier=state['volume_layers'][1]['id']
                event('volume_layer_style',id=identifier,colorscale='Blues',opacity=.5,percentile=40)
                event('volume_layout',mode='overlay');state=event('volume_scale',mode='shared')
                self.assertEqual(state['volume_mode'],'overlay');self.assertEqual(state['volume_scale'],'shared')
                before=w.volume_layers[1]
                w.handle_message(None,dict(event='volume_layer_style',payload=dict(id=identifier,opacity=2)),None)
                self.assertIn('error',w.send.call_args.args[0]);self.assertIs(w.volume_layers[1],before)
                state=event('volume_layer_remove',id=identifier);self.assertEqual(len(state['volume_layers']),1)

    def test_tile_pages_bound_scene_count_and_keep_layer_identity(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch,Mock
        from test_signal_recipes import make_acquisition
        from workspace import ExplorerWorkspace
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'a.h5';make_acquisition(path)
            with patch('workspace.get_plotlyjs',return_value=''),patch.object(ExplorerWorkspace,'figures',return_value={}):
                w=ExplorerWorkspace(path);w.send=Mock()
                for i in range(5):
                    w.handle_message(None,dict(event='comparison_add',payload=dict(intervals=[[1+i*.1,2+i*.1]],frames=[0,2])),None)
                    w.handle_message(None,dict(event='volume_layer_add',payload=dict(recipe_id=w.comparisons[-1]['recipe']['id'])),None)
                first=w.layered_figure((0,2));self.assertEqual(len(first.layout.meta['layers']),4)
                first_ids=[l['id'] for l in first.layout.meta['layers']]
                w.volume_page=1;second=w.layered_figure((0,2));self.assertEqual(len(second.layout.meta['layers']),2)
                self.assertFalse(set(first_ids)&{l['id'] for l in second.layout.meta['layers']})
                w.volume_page=0;again=w.layered_figure((0,2));self.assertEqual([l['id'] for l in again.layout.meta['layers']],first_ids)
                w.volume_layers=[];empty=w.layered_figure((0,2));self.assertEqual(len(empty.data),0);self.assertTrue(empty.layout.annotations)
